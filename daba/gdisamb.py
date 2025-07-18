#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Manual disambiguation editor
#
# Copyright (C) 2010—2021  Kirill Maslinsky <kirill@altlinux.org>
#
# This file is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
import codecs
import datetime
import itertools
import os
import re
import unicodedata
from collections import defaultdict, namedtuple

import wx.lib.colourselect as csel
import wx.lib.newevent
import wx.lib.scrolledpanel
import wx.stc

from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError
from intervaltree import IntervalTree

import daba.formats
import daba.grammar
from daba.ntgloss import Gloss


# EVENTS 

GlossSelectorEvent, EVT_SELECTOR_UPDATED = wx.lib.newevent.NewCommandEvent()
GlossButtonEvent, EVT_GLOSS_SELECTED = wx.lib.newevent.NewCommandEvent()
GlossEditEvent, EVT_GLOSS_EDITED = wx.lib.newevent.NewCommandEvent()
TokenSplitEvent, EVT_TOKEN_SPLIT = wx.lib.newevent.NewCommandEvent()
TokenJoinEvent, EVT_TOKEN_JOIN = wx.lib.newevent.NewCommandEvent()
TokenEditEvent, EVT_TOKEN_EDIT = wx.lib.newevent.NewCommandEvent()
SentenceJoinEvent, EVT_SENTENCE_JOIN = wx.lib.newevent.NewCommandEvent()
SentenceSplitEvent, EVT_SENTENCE_SPLIT = wx.lib.newevent.NewCommandEvent()
SentenceEditEvent, EVT_SENT_EDIT = wx.lib.newevent.NewCommandEvent()
SentAttrsEditEvent, EVT_SATTRS_EDIT = wx.lib.newevent.NewCommandEvent()
ShowSelectorEvent, EVT_SHOW_SELECTOR = wx.lib.newevent.NewCommandEvent()
SaveResultsEvent, EVT_SAVE_RESULTS = wx.lib.newevent.NewCommandEvent()
LocaldictLookupEvent, EVT_LOCALDICT_LOOKUP = wx.lib.newevent.NewCommandEvent()
LocaldictSaveEvent, EVT_LOCALDICT_SAVE = wx.lib.newevent.NewCommandEvent()

global bamananGV, maninkaGV 
bamananGV=True # JJM - default value for Gloss Validations specific to Bamanan
maninkaGV=False # JJM 24/03/2024  Settings should be saved

# UTILITY functions and no-interface classes

def normalizeText(t):
    """decompose all unicode accents in a string"""
    return unicodedata.normalize('NFKD', str(t))


TokenEdit = namedtuple('TokenEdit', 'operation start end toklist')


def get_basename(fname):
    """strip filename from extensions, including composite daba ones
like .pars.html and .dis.html"""
    basename = os.path.splitext(os.path.basename(fname))[0]
    pars = basename.rfind('.pars')
    repl = basename.rfind('.repl')  # added JJM
    if pars > 0:
        return basename[:pars]
    elif repl > 0:
        return basename[:repl]
    dis = basename.rfind('.dis')
    if dis > 0 and len(basename)-dis <= 7:
        return basename[:dis]
    return basename


class NormalizedTextCtrl(wx.TextCtrl):
    """TextCtrl with all text forced to Unicode NFKD (decomposed) form"""
    def __init__(*args, **kwargs):
        if len(args) > 3:
            arglist = list(args)
            arglist[3] = normalizeText(args[3])
        if 'value' in kwargs:
            kwargs['value'] = normalizeText(kwargs['value'])

        wx.TextCtrl.__init__(*args, **kwargs)

    def SetValue(self, string):
        """set widget's value to a Unicode NFKD-transformed string"""
        wx.TextCtrl.SetValue(self, normalizeText(string))


def makeGlossString(gloss, morphemes=False):
    """string representation of the Gloss object (for labelling buttons and the like)"""
    # print("makeGlossString morphemes passed:",morphemes)
    # print("makeGlossString gloss.morphemes passed:",gloss.morphemes)
    # print("makeGlossString gloss._str_ passed:",str(gloss))
    if not ''.join(gloss.ps) and not gloss.gloss and not gloss.morphemes:
        return gloss.form
    elif morphemes and gloss.morphemes:
        return u'{0} ({1}){3}{2}{4}'.format(gloss.form,
                                            '/'.join(gloss.ps), gloss.gloss, os.linesep, '\n' +
                                            os.linesep.join([str(m) for m in gloss.morphemes]))
    else:
        return u'{0} ({1}){3}{2}'.format(gloss.form,
                                         '/'.join(gloss.ps), gloss.gloss, os.linesep)


class SentAnnot(object):
    """a container for all sentence-level annotation data and state

    Attributes
    ----------
    pnum (int) : paragraph number (0-based)
    snum (int) : sentence number (0-based)
    senttoken (PlainToken) : sentence token
    senttext (str) : sentence text
    glosslist ([WordToken]) : list of annotations for each token in a sentence
    selectlist ([[WordToken]]) : list of annotations selected by user (for each token)
    attrs (dict) : sentence-level attributes (proxy to senttoken.attrs)
    """
    def __init__(self, pnum, snum, sent):
        """initialize from a compatibility-style sent"""
        self.pnum = pnum
        self.snum = snum
        self.senttoken, self.glosslist = sent
        self.senttext = self.senttoken.value
        self.selectlist = [[] for g in self.glosslist]
        self.attrs = self.senttoken.attrs

    def as_tuple(self):
        """return data as tuple for compatibility"""
        return (self.senttoken, self.selectlist, self.glosslist, (self.pnum, self.snum))

    def join(self, other):
        """join with another sentence, together with all annotation and attributes

        NB: side-effect, changes values of the object in-place
        """
        if self.attrs:
            if other.attrs:
                for k in self.attrs.keys():
                    if k in other.attrs:
                        self.attrs[k] = ' '.join([self.attrs[k], other.attrs[k]])
                for j in other.attrs.keys():
                    if j not in self.attrs:
                        self.attrs[j] = other.attrs[j]
        elif other.attrs:
            self.attrs = other.attrs
        self.senttext = ' '.join([self.senttext.strip(), other.senttext.strip()])
        toktuple = (self.senttoken.type, self.senttext)
        self.senttoken = daba.formats.PlainToken(toktuple, self.attrs)
        self.glosslist.extend(other.glosslist)
        self.selectlist.extend(other.selectlist)
        return self

    def split(self, tnum, charpos):
        """split sentence into two SentAnnot objs at the given point
        
        NB: side-effect: truncates own values and returns both self and new SentAnnot"""
        firsttext = self.senttext[:charpos].strip()
        secondtext = self.senttext[charpos:].strip()
        self.senttext = firsttext
        toktuple = (self.senttoken.type, self.senttext)
        self.senttoken = daba.formats.PlainToken(toktuple, self.attrs)
        newtoktuple = (self.senttoken.type, secondtext)
        newsenttoken = daba.formats.PlainToken(newtoktuple, self.attrs)
        firstglosslist = self.glosslist[:tnum]
        secondglosslist = self.glosslist[tnum:]
        self.glosslist = firstglosslist
        newsent = SentAnnot(self.pnum, self.snum+1, (newsenttoken, secondglosslist))
        firstselectlist = self.selectlist[:tnum]
        secondselectlist = self.selectlist[tnum:]
        self.selectlist = firstselectlist
        newsent.selectlist = secondselectlist
        return (self, newsent)


class FileParser(object):
    """A wrapper class for file IO operations and for keeping annotated data

    Attributes
    ----------
    dirty (bool) : user made some changes
    glosses ([SentAnnot]) : glosses data as a list of SentAnnot objects
    metadata (dict) : file metadata
    """
    def __init__(self):
        self.glosses = []
        self.dirty = False

    def read_file(self, filename):
        """read daba html file and store annotated data as a list of tuples in self.glosses"""
        freader = daba.formats.HtmlReader(filename)
        self.metadata = freader.metadata
        self.glosses = []
        snum = 0
        for pnum, par in enumerate(freader.glosses):
            for i, sent in enumerate(par):
                self.glosses.append(SentAnnot(pnum, snum, sent))
                self.numsent = freader.numsent
                self.numwords = freader.numwords
                snum += 1

    def write(self, filename):
        """write disabmiguated data into filename"""
        out = [[]]
        for sent in self.glosses:
            if sent.pnum > len(out)-1:
                out.append([])
            outgloss = []
            for selectlist, glosstoken in zip(sent.selectlist, sent.glosslist):
                if not selectlist:
                    outgloss.append(glosstoken)
                else:
                    if glosstoken.type == 'w':
                        glosstoken.setGlosslist(selectlist)
                    outgloss.append(glosstoken)
            out[-1].append((sent.senttoken, outgloss))
        # added JJM from format HtmlReader (removed numpar, unkown here)
        # these were not updated on save (only on load)
        for k, v in [
                ('_auto:words', self.numwords),
                ('_auto:sentences', self.numsent)
                ]:
            self.metadata[k] = str(v)

        fwriter = daba.formats.HtmlWriter((self.metadata, out), filename)
        fwriter.write()

    

class EditLogger(object):
    """log token edit operations"""
    def __init__(self, filename, encoding='utf-8'):
        """append logging data to a given file"""
        self.fileobj = codecs.open(filename, 'a+', encoding=encoding)

    @property
    def timestamp(self):
        """timestamp for logging records"""
        return datetime.datetime.now().isoformat()

    def LogEdit(self, firstgloss, secondgloss):
        """log gloss edition"""
        self.fileobj.write(u'{0}\n'.format('\t'.join([self.timestamp, 'edit', str(firstgloss), str(secondgloss)])))

    def LogSplit(self, srctoken, tokentuple):
        """log token split"""
        self.fileobj.write(u'{0}\n'.format('\t'.join([self.timestamp, 'split', srctoken, ''.join(tokentuple)])))

    def LogJoin(self, srctuple, restoken):
        """log token join"""
        self.fileobj.write(u'{0}\n'.format('\t'.join([self.timestamp, 'join', ''.join(srctuple), restoken])))

    def OnExit(self):
        """close log file on exit"""
        self.fileobj.close()


class SearchTool(object):
    """class for searching strings in annotated data"""
    def __init__(self, processor):
        """processor — FileParser object wrapping list of glosses"""
        self.processor = processor
        self.history = []
        self.matches = []
        self.position = 0
        self.ignorecase = True
        self.searchstr = ""

    @property
    def nmatches(self):
        """property holding the number of mathces"""
        return len(self.matches)

    def _searcher(self, searchstr, searchtype, startsent):
        """class-internal search engine"""
        self.position = 0
        self.matches = []
        self.searchstr = searchstr
        self.history.append(self.searchstr)
        if searchtype not in ('gf','in','re',) and self.ignorecase:
            searchstr = searchstr.lower()
        glosses = self.processor.glosses
        if startsent:
            glosses = glosses[startsent:] + glosses[:startsent]
        for sent in glosses:
            if searchtype == 'word part':
                for wnum, word in enumerate(sent.glosslist):
                    try:
                        if self.searchstr in word.token:
                            match = (sent.snum, wnum)
                            self.matches.append(match)
                    # FIXME: should not happen if all words are proper GlossTokens
                    except (AttributeError):
                        print(word)
            elif searchtype == "ps":
                for wnum, word in enumerate(sent.glosslist):
                    try:
                        s0=":"+self.searchstr+":"
                        if s0 in str(word.gloss) :
                            match = (sent.snum, wnum)
                            self.matches.append(match)
                    # FIXME: should not happen if all words are proper GlossTokens
                    except (AttributeError):
                        print(word)
            elif searchtype == "gf":
                for wnum, word in enumerate(sent.glosslist):
                    try:
                        s1=":"+self.searchstr+" "
                        s2=":"+self.searchstr+"]"
                        sgloss=str(word.gloss)+" "
                        if s1 in sgloss or s2 in sgloss :
                            match = (sent.snum, wnum)
                            self.matches.append(match)
                    # FIXME: should not happen if all words are proper GlossTokens
                    except (AttributeError):
                        print("except in searcher searchtype 'gf' :",word)              
            elif searchtype == "lx":
                for wnum, word in enumerate(sent.glosslist):
                    try:
                        s1=self.searchstr+":"
                        s2="["+s1
                        s3=" "+s1
                        sgloss=str(word.gloss)
                        if sgloss.startswith(s1) or s2 in sgloss or s3 in sgloss:
                            match = (sent.snum, wnum)
                            self.matches.append(match)
                    # FIXME: should not happen if all words are proper GlossTokens
                    except (AttributeError):
                        print("except in searcher searchtype 'lx' :",word)
            elif searchtype == "in":
                for wnum, word in enumerate(sent.glosslist):
                    try:
                        sgloss=str(word.gloss)
                        if searchstr in sgloss:
                            match = (sent.snum, wnum)
                            self.matches.append(match)
                    # FIXME: should not happen if all words are proper GlossTokens
                    except (AttributeError):
                        print("except in searcher searchtype 'in' :",searchstr,word)
            elif searchtype == "re":
                # print("_searcher 're' searchstr:",searchstr)
                for wnum, word in enumerate(sent.glosslist):
                    try:
                        sgloss=str(word.gloss)
                        # print("_searcher 're' sgloss:",sgloss, re.search(searchstr,sgloss))
                        if re.search(searchstr,sgloss):
                            match = (sent.snum, wnum)
                            self.matches.append(match)
                    # FIXME: should not happen if all words are proper GlossTokens
                    except (AttributeError):
                        print("except in searcher searchtype 're' :",searchstr,word)
            elif searchtype == 'sentence part':
                for matchobj in re.finditer(self.searchstr, sent.senttext):
                    self.matches.append((sent.snum, matchobj))
        return self.matches
        
    def find(self, searchstr, startsent=0):
        """search for a given string 

        By default, a query is interpreted as a word part. It is
        treated as a sentence part in case query contains spaces.

        Returns sentence match position tuple (sentid, tokid)
        """
        if ' ' in searchstr:
            searchtype = 'sentence part'
        elif searchstr.startswith(':::'):
            searchtype = "gf"
            searchstr=normalizeText(searchstr[3:])
        elif searchstr.startswith('::'):
            searchtype = "ps"
            searchstr=searchstr[2:]
        elif searchstr.startswith(":"):
            searchtype='lx'
            searchstr=searchstr[1:]
        elif searchstr.startswith('**'):
            searchtype = "re"
            searchstr=searchstr[2:]
        elif searchstr.startswith("*"):
            searchtype='in'
            searchstr=searchstr[1:]
        else:
            searchtype = 'word part'
        matches = self._searcher(searchstr, searchtype, startsent)
        if matches:
            return matches[0]
        else:
            return ()

    def findNext(self):
        """return next match position tuple (sentid, tokid)"""
        if self.matches:
            self.position += 1
            if self.position >= len(self.matches):
                self.position -= len(self.matches)
            return self.matches[self.position]
        else:
            return ()

    def findPrev(self):
        """return previous match position tuple (sentid, tokid)"""
        if self.matches:
            self.position -= 1
            if self.position < 0:
                self.position = len(self.matches) + self.position
            return self.matches[self.position]
        else:
            return ()


# WIDGETS

class SentText(wx.StaticText):
    """Sentence text overview widget"""
    def __init__(self, parent, id, num=None, *args, **kwargs):
        wx.StaticText.__init__(self, parent, *args, **kwargs)
        self.num = num
        self.parent = parent

    def onMouseEvent(self, event):
        """left-click on a word in SentText bring corresponding selection
buttons into view on canvas (if not visible)"""
        if event.Moving():
            self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        elif event.LeftDown():
            self.GetTopLevelParent().sentpanel.OnSaveResults(event)
            self.GetTopLevelParent().ShowSent(self.num)
            self.GetTopLevelParent().Layout()
            self.GetTopLevelParent().notebook.ChangeSelection(0)   # added JJM: switches to sentpanel
        event.Skip()

class MetaText(wx.StaticText):
    """Meta data overview widget"""
    def __init__(self, parent, id, num=None, *args, **kwargs):
        wx.StaticText.__init__(self, parent, *args, **kwargs)
        self.num = num
        self.parent = parent

        font = wx.Font(12, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(font)


    """def onMouseEvent(self, event):
        
        if event.Moving():
            self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        elif event.LeftDown():
            self.GetTopLevelParent().metapanel.OnSaveResults(event)
            self.GetTopLevelParent().ShowSent(self.num)
            self.GetTopLevelParent().Layout()

        event.Skip()
    """

class GlossButton(wx.Panel):
    """Single button widget for selecting a gloss variant
    
    For a Gloss that contains morphemes the widget generates
    nested GlossButtons recursively for each morpheme.

    Attributes
    ----------
    selected (bool) : gloss is selected
    children (list) : a list of the nested morphemes of a gloss
    gloss (Gloss) : widget's Gloss
"""
    def __init__(self, parent, gloss, statecolours, disabled=False, addbylocaldict=False,
                 *args, **kwargs):
        """GlossButton constructor

        :param gloss: Gloss to be displayed on the button
        :type gloss: Gloss
        :param statecolors: colors for various state of the selector
        :type statecolors: dict"""
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.selected = False
        self.children = []
        self.gloss = gloss
        self.disabled = disabled
        self.statecolours = statecolours
        self.addbylocaldict = addbylocaldict

        box = wx.BoxSizer(wx.VERTICAL)
        # prepare main gloss button
        textforbutton=makeGlossString(gloss)
        if self.addbylocaldict: textforbutton="*"+textforbutton
        if self.disabled:
            self.main = wx.Button(self, -1, textforbutton)
            self.main.Disable()
        else:
            self.main = wx.ToggleButton(self, -1, textforbutton)
            self.main.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggled)
        fore, back = self.statecolours['deselected']
        self.main.SetForegroundColour(fore)
        if self.addbylocaldict: 
            self.main.SetBackgroundColour((255, 230, 200, 255)) # some sort of beige?
        else:
            self.main.SetBackgroundColour(back)
        self.Refresh()
        box.Add(self.main, 0, wx.EXPAND)
        # prepare morphemes buttons recursively
        if gloss.morphemes:
            morphemes = wx.BoxSizer(wx.HORIZONTAL)
            for morph in gloss.morphemes:
                m = GlossButton(self, morph, self.statecolours,
                                disabled=self.disabled)
                self.children.append(m)
                morphemes.Add(m, 0)
            box.Add(morphemes, 0)

        self.SetSizer(box)

    def OnToggled(self, event):
        """Button pressed by the user"""
        evt = GlossButtonEvent(self.GetId())
        evt.SetEventObject(self)
        wx.PostEvent(self.GetEventHandler(), evt)
        self.DoToggle()

    def DoToggle(self):
        """programmatically push button"""
        self.selected = not self.selected
        if self.selected:
            fore, back = self.statecolours['selected']
            self.main.SetForegroundColour(fore)
            if self.addbylocaldict:
                self.main.SetBackgroundColour((255, 230, 200, 255)) # some sort of beige?
            else:
                self.main.SetBackgroundColour(back)
        else:
            fore, back = self.statecolours['deselected']
            self.main.SetForegroundColour(fore)
            if self.addbylocaldict:
                self.main.SetBackgroundColour((255, 230, 200, 255)) # some sort of beige?
            else:
                self.main.SetBackgroundColour(back)
        self.Refresh()
        self.ToggleChildren()

    def ToggleChildren(self):
        """propagate toggle to the nested morpheme buttons"""
        for child in self.children:
            if bool(child.main.GetValue()) != self.selected:
                child.main.SetValue(self.selected)
                child.DoToggle()


class GlossInputDialog(wx.Dialog):
    """Dialog to edit gloss manually

    Attributes
    ----------
    as_gloss (Gloss) : current gloss selected/entered in the dialog
    glossstring (str) : dialog's gloss converted into string representation
    morphemes (list) : list of nested morpheme widgets
    save (bool) : save entered gloss into localdict (default: true)

    Widgets
    -------
    glosstext (wx.ComboBox) : widget to edit gloss in text form
    gbutton (GlossButton) : button visualizing gloss structure (non-pressable)
    """
    def __init__(self, parent, id, title, gloss, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title,
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                           *args, **kwargs)

        self.as_gloss = gloss
        self.morphemes = []
        self.save = True
        self.freeze = False
        config = wx.Config.Get()
        self.statecolors = {'deselected': (
            config.Read('colors/deselected/fore', 'Black'),
            config.Read('colors/deselected/back', 'White'))}

        vbox_top = wx.BoxSizer(wx.VERTICAL)
        global bamananGV,maninkaGV
        texte_à_afficher="Composez votre glose | x:ps:gloss [y...] | Gloss string"
        if bamananGV: texte_à_afficher="(bam) "+texte_à_afficher
        elif maninkaGV: texte_à_afficher="(emk) "+texte_à_afficher
        vbox_top.Add(wx.StaticText(self, wx.ID_ANY,
                                   texte_à_afficher,size=(600,20)))  # JJM dirty trick to enlarge dialog
        glossstring = str(self.as_gloss)
        self.glosstext = wx.ComboBox(self, wx.ID_ANY, glossstring,
                                     choices=[glossstring])
        vbox_top.Add(self.glosstext, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)
        self.gbutton = GlossButton(self, self.as_gloss, self.statecolors, disabled=True)
        vbox_top.Add(self.gbutton)
        cb = wx.CheckBox(self, -1, "Save to localdict")
        cb.SetValue(True)
        vbox_top.Add(cb, 0, wx.TOP | wx.BOTTOM, 10)

        cb.Bind(wx.EVT_CHECKBOX, self.OnCheckLocaldict)
        self.glosstext.Bind(wx.EVT_TEXT, self.OnEditGlosstext)
        self.glosstext.Bind(wx.EVT_COMBOBOX, self.OnEditGlosstext)
        self.glosstext.Bind(wx.EVT_TEXT_ENTER, self.OnEditGlosstext)

        vbox_top.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(vbox_top)
        self.Fit()
        self.Layout()

    def FitGlosstextWidth(self):
        """resize gloss edit area for a width of the gloss text"""
        gwidth, gheight = self.glosstext.GetTextExtent(self.glosstext.GetValue())
        self.GetSizer().SetItemMinSize(self.glosstext, (gwidth + 15, gheight + 10))
        self.Layout()
        self.Fit()
   
    def tomonolith(m) :
        mapping = { 'à':'à', 'â':'â', 'é':'é', 'ê':'ê', 'è':'è', 'ë':'ë', 'î':'î', 'ï':'ï', 'ô':'ô', 'û':'û', 'ù':'ù', 'ç':'ç', 'À':'À', 'Ç':'Ç', 'Ê':'Ê', 'Ô':'Ô'}
        lxps=m.groups()[0]
        gloss=m.groups()[1]
        for k, v in mapping.items():
            if k in gloss:
                gloss = gloss.replace(k, v)
        return lxps+gloss

    def UpdateInterface(self, gloss):
        """
        def tomonolith(m) :
            mapping = { 'à':'à', 'â':'â', 'é':'é', 'ê':'ê', 'è':'è', 'ë':'ë', 'î':'î', 'ï':'ï', 'ô':'ô', 'û':'û', 'ù':'ù', 'ç':'ç', 'À':'À', 'Ç':'Ç', 'Ê':'Ê', 'Ô':'Ô'}
            lxps=m.groups()[0]
            gloss=m.groups()[1]
            for k, v in mapping.items():
                if k in gloss:
                    gloss = gloss.replace(k, v)
            return lxps+gloss
        """
        """update dialog (gbutton, glosstext) given a gloss"""
        self.freeze = True
        glossstring = str(gloss)  # ou bien self.glosstext ?
        # glossstring = re.sub(r'([^\:\[ ]+\:[^\:\[ ]*\:)([^\: ]+)',tomonolith,glossstring) # JJM temp fix
        cursor = self.glosstext.GetInsertionPoint()
        #print("'"+glossstring+"', len(glossstring):",len(glossstring), ", cursor:", cursor)
        diacritics="\u0301\u0300\u0302\u030c\u00B8\u0308\u005e\u02c6"  # high, low, decreasing, increasing tone diacritics + cedilla and diaeresis (trema as in ë)
        #print("fin de glossstring=",glossstring[-1])
        if glossstring[-1] in diacritics:
            cursor=len(glossstring) # JJM in case monolith characters are split : ê -> e ̂              
        elif cursor<len(glossstring) :
            if glossstring[cursor] in diacritics:
                cursor=cursor+1
        # cette logique marche sous windows, ne marche plus sous linux 31/12/2024
        # still valid after tomonolith? for lexeme ?

        self.glosstext.SetValue(glossstring)
        self.glosstext.SetInsertionPoint(cursor)
        sizer = self.GetSizer()
        sizer.Detach(self.gbutton)
        self.gbutton.Show(False)
        self.gbutton = GlossButton(self, gloss, self.statecolors, disabled=True)
        sizer.Insert(2, self.gbutton)
        self.FitGlosstextWidth()
        self.freeze = False

    def ShowLocaldictVariants(self, savedglosses):
        """populate glosstext selection list with items from localdict"""
        for gloss in savedglosses:
            if not gloss == self.as_gloss:
                self.glosstext.Append(str(gloss))

    def SetGlossAttr(self, **kwargs):
        """deprecate: unused"""
        self.as_gloss._replace(**kwargs) 

    def GetGloss(self):
        """return current dialog's Gloss"""
        return self.as_gloss

    def OnEditGlosstext(self, evt):
        """gloss is edited event callback"""

        def normalizeLex(m):
            lx=m.groups()[0]
            lx=normalizeText(lx)
            psgloss=m.groups()[1]
            psgloss=unicodedata.normalize('NFC',psgloss) # is this faster than tomonolith() ?
            return lx+psgloss

        if not self.freeze:
            self.FitGlosstextWidth()
            # glosstext = normalizeText(self.glosstext.GetValue())  # should NOT be applied to 3d part (gloss in French)
            glosstext = self.glosstext.GetValue()
            glosstext = re.sub(r'([^\:\[ ]+)(\:[^\:\[ ]*\:[^\:\[\] ]*)',normalizeLex,glosstext)
            oldgloss = self.as_gloss
            try:
                toks = daba.grammar.str_tokenize(glosstext)   # cf same process in formats / glosstext_to_html
                self.as_gloss = daba.grammar.stringgloss_parser().parse(toks)
                if not self.as_gloss == oldgloss:
                    # is this the good place to :
                    #   check mrph values for bambara here (in ['INF','QUOT','EQU','PFV.TR',...])
                    # needs config setting to enable/disable bambara
                    # try for now
                    #print("bamananGV:",bamananGV,"    maninkaGV:",maninkaGV)
                    if bamananGV:
                        mrphlist=["la:mrph:à","la:mrph:CAUS","lá:mrph:CAUS","lán:mrph:CAUS","ná:mrph:CAUS","rɔ́:mrph:CAUS","mà:mrph:SUPER","màn:mrph:SUPER","rɔ́:mrph:IN","lu:mrph:PL2","nu:mrph:PL2","ba:mrph:AUGM","baa:mrph:AG.OCC","baga:mrph:AG.OCC","bali:mrph:PTCP.NEG","ka:mrph:GENT","la:mrph:AG.PRM","na:mrph:AG.PRM","la:mrph:LOC","na:mrph:LOC","la:mrph:PRIX","na:mrph:PRIX","la:mrph:MNT1","na:mrph:MNT1","lata:mrph:MNT2","nata:mrph:MNT2","la:mrph:PROG","na:mrph:PROG","la:mrph:PFV.INTR","na:mrph:PFV.INTR","n':mrph:PFV.INTR","ra:mrph:PFV.INTR","rá:mrph:IN","rɔ́:mrph:IN","w:mrph:PL","lama:mrph:STAT","nama:mrph:STAT","lan:mrph:INSTR","nan:mrph:INSTR","len:mrph:PTCP.RES","nen:mrph:PTCP.RES","li:mrph:NMLZ","ni:mrph:NMLZ","\\:mrph:NMLZ2","ma:mrph:COM","ma:mrph:RECP.PRN","man:mrph:ADJ","ntan:mrph:PRIV","ma:mrph:DIR","nan:mrph:ORD","nin:mrph:DIM","nci:mrph:AG.EX","ɲɔgɔn:mrph:RECP","ɲwan:mrph:RECP","ta:mrph:PTCP.POT","tɔ:mrph:CONV","tɔ:mrph:ST","ya:mrph:DEQU","yɛ:mrph:DEQU","ya:mrph:ABSTR","ma:mrph:SUPER","man:mrph:SUPER","sɔ̀:mrph:EN","ra:mrph:OPT2","la:mrph:OPT2","na:mrph:OPT2"]
                        pmlist=["bɛ́nà:pm:FUT","bɛ́n':pm:FUT","bɛ:pm:IPFV.AFF","b':pm:IPFV.AFF","be:pm:IPFV.AFF","bi:pm:IPFV.AFF","bɛ́kà:pm:PROG.AFF","bɛ́k':pm:PROG.AFF","bɛ́ka:pm:INFR","bága:pm:INFR","bìlen:pm:COND.NEG","kà:pm:INF","k':pm:INF","ka:pm:SBJV","k':pm:SBJV","ka:pm:QUAL.AFF","man:pm:QUAL.NEG","kànâ:pm:PROH","kàn':pm:PROH","ma:pm:PFV.NEG","m':pm:PFV.NEG","mánà:pm:COND.AFF","mán':pm:COND.AFF","máa:pm:COND.AFF","nà:pm:CERT","n':pm:CERT","tɛ:pm:IPFV.NEG","te:pm:IPFV.NEG","ti:pm:IPFV.NEG","t':pm:IPFV.NEG","tɛ́kà:pm:PROG.NEG","tɛ́k':pm:PROG.NEG","tɛ́ka:pm:INFR.NEG","tɛ́k':pm:INFR.NEG","tɛ́nà:pm:FUT.NEG","tɛ́n':pm:FUT.NEG","ye:pm:PFV.TR","y':pm:PFV.TR","yé:pm:IPFV","yé:pm:IMP","y':pm:IMP","yékà:pm:RCNT","màa:pm:DES","mà:pm:DES","m':pm:DES"]
                        coplist=["bɛ́:cop:être","b':cop:être","yé:cop:être","kó:cop:QUOT","k':cop:QUOT","dòn:cop:ID","dò:cop:ID","tɛ́:cop:COP.NEG","té:cop:COP.NEG","t':cop:COP.NEG","yé:cop:EQU","y':cop:EQU","bé:cop:être"]
                        perslist=["ń:pers:1SG","nê:pers:1SG.EMPH","í:pers:2SG","í:pers:REFL","ê:pers:2SG.EMPH","à:pers:3SG","àlê:pers:3SG.EMPH","án:pers:1PL","ánw:pers:1PL.EMPH","a':pers:2PL","á:pers:2PL","á':pers:2PL","áw:pers:2PL.EMPH","ù:pers:3PL","òlû:pers:ce.PL2"]
                        # pplist=["bála:pp:sur","bálan:pp:sur","bára:pp:chez","bólo:pp:CNTRL","bólokɔrɔ:pp:sous.la.main [bólo:n:bras kɔ́rɔ:pp:sous]","cɛ́:pp:entre","cɛ́fɛ̀:pp:parmi [cɛ́:n:milieu fɛ̀:pp:par]","cɛ́la:pp:parmi [cɛ́:n:milieu lá:pp:à]","cɛ́mà:pp:parmi [cɛ́:n:milieu mà:pp:ADR]","dáfɛ̀:pp:auprès [dá:n:bouche fɛ̀:pp:par]","dála:pp:auprès [dá:n:bouche lá:pp:à]","fɛ̀:pp:par","jùfɛ̀:pp:sous [jù:n:derrière fɛ̀:pp:par]","jùkɔ́rɔ:pp:dessous [jù:n:derrière kɔ́rɔ:pp:sous]","jùlá:pp:à.l'endroit.de [jù:n:derrière lá:pp:à]","ka:pp:POSS","kàlamà:pp:au.courant.de [kàla:n:tige mà:pp:ADR]","kámà:pp:pour [kán:n:cou mà:pp:ADR]","kàn:pp:sur","kánmà:pp:pour [kán:n:cou mà:pp:ADR]","kánna:pp:sur [kán:n:cou lá:pp:à]","kɛ̀rɛfɛ̀:pp:par.côté [kɛ̀rɛ:n:côté fɛ̀:pp:par]","kósɔ̀n:pp:à.cause.de","kɔ́:pp:après","kɔ́fɛ̀:pp:derrière [kɔ́:n:dos fɛ̀:pp:par]","kɔ́kàn:pp:à.l'extérieur [kɔ́:n:dos kàn:pp:sur]","kɔ́kɔrɔ:pp:en.soutien.de [kɔ́:n:dos kɔ́rɔ:pp:sous]","kɔ́nɔ:pp:dans","kɔ́rɔ:pp:sous","kùn:pp:sur","kùnda:pp:du.côté.de [kùn:n:tête dá:n:bouche]","kùnfɛ̀:pp:à.l'aveugle [kùn:n:tête fɛ̀:pp:par]","kùnkàn:pp:à.propos.de [kùn:n:tète kàn:pp:sur]","kùnkɔ́rɔ:pp:pour [kùn:n:tête kɔ́rɔ:pp:sous]","kùnná:pp:au-dessus [kùn:n:tête lá:pp:à]","k':pp:POSS","lá:pp:à","lɔ́:pp:IN","mà:pp:ADR","ná:pp:à","nàgakɔ́rɔ:pp:à.proximité [nàga:n:ventre kɔ́rɔ:n:dessous]","nɔ́:pp:IN","nɔ̀fɛ̀:pp:derrière [nɔ̀:n:trace fɛ̀:pp:par]","nɔ̀kàn:pp:après [nɔ̀:n:trace kàn:pp:sur]","nɔ̀ná:pp:à.la.place.de [nɔ̀:n:trace lá:pp:à]","ɲɛ́:pp:devant","ɲɛ́fɛ̀:pp:devant [ɲɛ́:n:oeil fɛ̀:pp:par]","ɲɛ́kàn:pp:au.dam.de [ɲɛ́:n:oeil kàn:pp:sur]","ɲɛ́kɔrɔ:pp:en.présence.de [ɲɛ́:n:oeil kɔ́rɔ:pp:sous]","ɲɛ́mà:pp:devant [ɲɛ́:n:oeil mà:pp:ADR]","ɲɛ́na:pp:devant [ɲɛ́:n:oeil lá:pp:à]","rɔ́:pp:IN","sánfɛ̀:pp:par-dessus [sán:n:ciel fɛ̀:pp:par]","sènfɛ̀:pp:au.cours.de [sèn:n:jambe fɛ̀:pp:par]","sènkɔ́rɔ:pp:parmi [sèn:n:jambe kɔ́rɔ:pp:sous]","yé:pp:PP","yɔ́rɔ:pp:chez","y':pp:PP"]
                        #     morphemes cannot be checked against glosstext 
                        pplist=["bála:pp:sur","bálan:pp:sur","bára:pp:chez","bólo:pp:CNTRL","bólokɔrɔ:pp:sous.la.main","cɛ́:pp:entre","cɛ́fɛ̀:pp:parmi","cɛ́la:pp:parmi","cɛ́mà:pp:parmi","dáfɛ̀:pp:auprès","dála:pp:aupreès","fɛ̀:pp:par","jùfɛ̀:pp:sous","jùkɔ́rɔ:pp:dessous","jùlá:pp:à.l'endroit.de","ka:pp:POSS","kàlamà:pp:au.courant.de","kámà:pp:pour","kàn:pp:sur","kánmà:pp:pour","kánna:pp:sur","kɛ̀rɛfɛ̀:pp:par.côté","kósɔ̀n:pp:à.cause.de","kɔ́:pp:après","kɔ́fɛ̀:pp:derrière","kɔ́kàn:pp:à.l'extérieur","kɔ́kɔrɔ:pp:en.soutien.de","kɔ́nɔ:pp:dans","kɔ́rɔ:pp:sous","kùn:pp:sur","kùnda:pp:du.côté.de","kùnfɛ̀:pp:à.l'aveugle","kùnkàn:pp:à.propos.de","kùnkɔ́rɔ:pp:pour","kùnná:pp:au.dessus","k':pp:POSS","lá:pp:à","lɔ́:pp:IN","mà:pp:ADR","ná:pp:à","nàgakɔ́rɔ:pp:à.proximité","nɔ́:pp:IN","nɔ̀fɛ̀:pp:derrière","nɔ̀kàn:pp:après","nɔ̀ná:pp:à.la.place.de","ɲɛ́:pp:devant","ɲɛ́fɛ̀:pp:devant","ɲɛ́kàn:pp:au.dam.de","ɲɛ́kɔrɔ:pp:en.présence.de","ɲɛ́mà:pp:devant","ɲɛ́na:pp:devant","rɔ́:pp:IN","sánfɛ̀:pp:par-dessus","sènfɛ̀:pp:au.cours.de","sènkɔ́rɔ:pp:parmi","yé:pp:PP","yɔ́rɔ:pp:chez","y':pp:PP"]
                        # attention : ces gloses (le français) DOIVENT être en monolithes!
                        bamok=True
                        if ':mrph:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:mrph\:[^\s\]]*)',glosstext)
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in mrphlist:
                                        bamok=False
                                        break
                        elif ':pm:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:pm\:[^\s\]]*)',glosstext)  # this search does not take morphemes!
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in pmlist:
                                        bamok=False
                                        break
                        elif ':cop:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:cop\:[^\s\]]*)',glosstext)
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in coplist:
                                        bamok=False
                                        break
                        elif ':pers:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:pers\:[^\s\]]*)',glosstext)
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in perslist:
                                        bamok=False
                                        break
                        elif ':pp:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:pp\:[^\s\]]*)',glosstext)
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in pplist:
                                        bamok=False
                                        break
                        # ajouter conj,prn,dtm,...


                        if bamok:
                            self.glosstext.SetBackgroundColour(wx.NullColour)
                            self.glosstext.Refresh()
                            self.UpdateInterface(self.as_gloss)
                        else:
                            # print(" refusé: thismrph=",thismrph)
                            # value could be used in a help message in dialog box status bar
                            self.glosstext.SetBackgroundColour((254,216,177,255))   # was 'orange'denotes incorrect gloss for mrph light orange 254 216 177
                            self.glosstext.Refresh() 

                    elif maninkaGV:
                        mrphlist=["`:mrph:ART", "baa:mrph:AG.OCC", "ba:mrph:AUGM", "bali:mrph:PTCP.NEG", "d':mrph:AOR.INTR", "dá:mrph:AOR.INTR", "da:mrph:AOR.INTR", "d':mrph:AOR.INTR", "dɔ́:mrph:IN", "ka:mrph:GENT", "la:mrph:INF.LA", "l':mrph:INF.LA", "na:mrph:INF.LA", "n':mrph:INF.LA", "la:mrph:à", "la:mrph:AG.PRM", "la:mrph:LOC", "la:mrph:MNT1", "lama:mrph:STAT", "lan:mrph:INSTR", "lan:mrph:à", "lá:mrph:CAUS", "la:mrph:PRICE", "len:mrph:DIM", "li:mrph:NMLZ", "\\:mrph:NMLZ2", "lù:mrph:PL", "lú:mrph:PL", "ma:mrph:COM", "ma:mrph:RECP.PRN", "man:mrph:SUPER", "man:mrph:ADJ", "má:mrph:SUPER", "n':mrph:AOR.INTR", "na:mrph:AOR.INTR", "na:mrph:AG.PRM", "na:mrph:LOC", "na:mrph:MNT1", "nama:mrph:STAT", "nan:mrph:MNT1", "nan:mrph:INSTR", "nan:mrph:à", "ná:mrph:CAUS", "na:mrph:à", "nan:mrph:ORD", "nɛn:mrph:PTCP.RES", "nɛn:mrph:DIM", "ni:mrph:NMLZ", "nin:mrph:NMLZ", "nin:mrph:PTCP.RES", "nin:mrph:DIM", "nɔ́:mrph:IN", "ntan:mrph:PRIV", "nte:mrph:AG.EX", "nù:mrph:PL", "ɲa:mrph:ABSTR", "ɲa:mrph:DEQU", "ɲɔɔn:mrph:RECP", "r':mrph:AOR.INTR", "rá:mrph:AOR.INTR", "ra:mrph:AOR.INTR", "ran:mrph:INSTR", "ren:mrph:DIM", "rɔma:mrph:STAT", "rɔ́:mrph:IN", "san:mrph:IMMED", "ta:mrph:FOC.ADJ", "ta:mrph:PRICE", "ta:mrph:PTCP.POT", "tɔ:mrph:ST", "tɔ:mrph:CONV.PROG", "ya:mrph:ABSTR", "ya:mrph:DEQU"]
                        pmlist=["b':pm:COND", "báa:pm:COND", "bá:pm:COND", "báda:pm:PRF", "bád':pm:PRF", "bàli:pm:sinon", "bàni:pm:sinon", "bánsan:pm:IMMED.TR", "bár':pm:PRF", "bára:pm:PRF", "bɛ́n':pm:FUT.AFF1", "bɛ́nà:pm:FUT.AFF1", "d':pm:FUT.HAB", "dí:pm:FUT.HAB", "dín`:pm:FUT.AFF2", "dínà:pm:FUT.AFF2", "k`:pm:INF.KA", "k':pm:INF.KA", "k`:pm:AOR", "k':pm:AOR", "k':pm:PROH", "k':pm:QUAL.AFF", "kà:pm:INF.KA", "kà:pm:AOR", "ká:pm:PROH", "ká:pm:QUAL.AFF", "kánà:pm:SBJV.NEG", "m`:pm:OPT", "m':pm:PFV.NEG", "mà:pm:OPT", "má:pm:PFV.NEG", "bɛ́:pm:PFV.AFF", "b':pm:PFV.AFF", "mán:pm:QUAL.NEG", "mánà:pm:COND", "n`:pm:AOR2", "nà:pm:AOR2", "nɔ̀:pm:AOR2", "ɲ':pm:SBJV", "ɲé:pm:SBJV", "tén`:pm:FUT.NEG", "ténà:pm:FUT.NEG", "tén':pm:FUT.NEG", "té:pm:COP.NEG2", "tɛ̀dɛ:pm:PST2", "tɛ̀d':pm:PST2", "tɛ́:pm:COP.NEG2", "tɛ́:pm:IPFV.NEG", "tɛ́n':pm:FUT.NEG", "tɛ́nà:pm:FUT.NEG", "tɛ̀r':pm:PST2", "tɛ̀rɛ:pm:PST2", "y':pm:SBJV", "yé:pm:HAB", "yé:pm:SBJV"]
                        coplist=["bɛ́:cop:être", "k':cop:QUOT", "kàn:cop:dire", "kó:cop:QUOT", "ɲ':cop:COP", "ɲé:cop:COP", "t':cop:COP.NEG2", "té:cop:COP.NEG2", "tɛ́:cop:COP.NEG1", "t':cop:COP.NEG1","y':cop:COP", "yé:cop:COP", "tɛ̀dɛ:cop:COP.PST", "tɛ̀d':cop:COP.PST"]
                        perslist=["à:pers:3SG", "àlê:pers:3SG.EMPH", "àlelu:pers:3SG.EMPH", "álelu:pers:2SG.EMPH", "àlu:pers:3PL", "álú:pers:2PL", "ân:pers:1PL", "ándèlu:pers:1PL.EMPH", "ánnù:pers:1PL.EMPH", "àyi:pers:3PL", "áyi:pers:2PL", "áyì:pers:2PL", "élê:pers:2SG.EMPH", "í:pers:2SG", "í:pers:REFL", "ílê:pers:2SG.EMPH", "ǹ:pers:1PL", "ń:pers:1SG", "nê:pers:1SG.EMPH"]
                        pplist=["báda:pp:chez", "bára:pp:chez", "bólo:pp:CNTRL", "bólofɛ̀:pp:à.part", "bólomà:pp:pour", "bɔ̀ɔfɛ:pp:à.côté", "bɔ́ɔntɛ:pp:à.part", "bɔ́ɔtɛ:pp:à.part", "dí:pp:PP", "dáfɛ̀:pp:près.de", "dɔ́:pp:dans", "fɛ̀:pp:avec", "kàlamà:pp:au.courant.de", "kámà:pp:pour", "kánmà:pp:pour", "kàn:pp:sur", "kósɔ̀n:pp:à.cause.de", "kɔ́:pp:derrière", "kɔ́dɔ:pp:sous", "kɔ́fɛ̀:pp:après", "kɔ́kàn:pp:à.l'extérieur", "kɔ́kɔdɔ:pp:derrière", "kɔ́kɔrɔ:pp:derrière", "kɔ́mà:pp:dehors", "kɔ́nɔ:pp:à.l’intérieur", "kɔ́rɔ:pp:sous", "kɔ́tɔ:pp:derrière", "kùn:pp:à", "kùndɔ:pp:au-dessus", "kùnna:pp:au-dessus", "kùnnɔ:pp:au-dessus", "l':pp:à", "lá:pp:à", "mà:pp:sur", "n':pp:à", "ná:pp:à", "nɔ́:pp:dans", "ɲáfɛ̀:pp:en.surface.partout", "ɲákɔdɔ:pp:devant", "ɲákɔtɔ:pp:hors.vision", "ɲána:pp:selon", "ɲɛ́:pp:devant", "rɔ́:pp:dans", "sándɔ:pp:au-dessus", "sènfɛ̀:pp:en.plus.de", "tɛ́:pp:entre", "tɛ́mà:pp:parmi", "tɔ̀ɔfɛ̀:pp:près.de", "tɔ́ɔtɛ:pp:à.part", "tɔ̀rɔfɛ̀:pp:près.de", "yé:pp:pour"]
                        # attention : ces gloses (en français) DOIVENT être en monolithes!
                        emkok=True
                        if ':mrph:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:mrph\:[^\s\]]*)',glosstext)
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in mrphlist:
                                        emkok=False
                                        break
                        elif ':pm:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:pm\:[^\s\]]*)',glosstext)  # this search does not take morphemes!
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in pmlist:
                                        emkok=False
                                        break
                        elif ':cop:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:cop\:[^\s\]]*)',glosstext)
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in coplist:
                                        emkok=False
                                        break
                        elif ':pers:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:pers\:[^\s\]]*)',glosstext)
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in perslist:
                                        emkok=False
                                        break
                        elif ':pp:' in glosstext:
                            allbam=re.findall(r'([^\[\s\:]+\:pp\:[^\s\]]*)',glosstext)
                            if allbam:
                                for thisbam in allbam:
                                    if thisbam not in pplist:
                                        emkok=False
                                        break
                        # ajouter conj,prn,dtm,...


                        if emkok:
                            # if thisbam: print(" accepté: thismrph=",thisbam)
                            self.glosstext.SetBackgroundColour(wx.NullColour)
                            self.glosstext.Refresh()
                            self.UpdateInterface(self.as_gloss)
                        else:
                            # if thisbam: print(" refusé: thismrph=",thisbam)
                            # value could be used in a help message in dialog box status bar
                            self.glosstext.SetBackgroundColour((254,216,177,255))   # was 'orange'denotes incorrect gloss for mrph light orange 254 216 177
                            self.glosstext.Refresh() 

                    else:  # no validation
                        self.glosstext.SetBackgroundColour(wx.NullColour)
                        self.glosstext.Refresh()
                        self.UpdateInterface(self.as_gloss)
                else:
                    self.glosstext.SetBackgroundColour('yellow')   # denotes incorrect ps tag
                    self.glosstext.Refresh()
            except (LexerError, NoParseError):
                self.glosstext.SetBackgroundColour('pink')    # denotes incomplete/incorrect syntax
                self.glosstext.Refresh()
            # JJM try real time update of dialog's lookup Here ?


    def OnCheckLocaldict(self, evt):
        """toggle `save to localdict` flag"""
        self.save = not self.save


class TokenSplitDialog(wx.Dialog):
    """dialog to enter token split position

    Attributes
    ----------
    form (str) : token string
    split (tuple) : a tuple of token string parts after split

    Widgets
    -------
    formfield (NormalizedTextCtrl) : field used to indicate token split position
    splitbutton (wx.Button) : button binded to split action
    """
    def __init__(self, parent, form, *args, **kwargs):
        wx.Dialog.__init__(self, parent, -1, "Split gloss")
        self.form = form
        self.split = (self.form,)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(wx.StaticText(self, -1, "Move cursor to the split point:"))
        self.formfield = NormalizedTextCtrl(self, -1, self.form, style=wx.TE_READONLY)
        self.formfield.SetInsertionPoint(0)
        self.splittext = wx.StaticText(self, -1, self.form)
        vbox.Add(self.formfield)
        vbox.Add(self.splittext)
        splitbutton = wx.Button(self, -1, "Split")
        vbox.Add(splitbutton)
        vbox.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0)
        self.SetSizer(vbox)

        splitbutton.Bind(wx.EVT_BUTTON, self.OnSplit)

    def OnSplit(self, evt):
        """callback for token split action"""
        pos = self.formfield.GetInsertionPoint()
        last = self.formfield.GetLastPosition()
        if not pos == 0 and not pos == last:
            first = self.formfield.GetRange(0, pos)
            second = self.formfield.GetRange(pos, last)
            self.split = (first, second)
            sizer = self.GetSizer()
            sizer.Detach(self.splittext)
            self.splittext.Show(False)
            self.splittext = wx.StaticText(self, wx.ID_ANY, ' | '.join(self.split))
            sizer.Insert(2, self.splittext, 0, wx.EXPAND)
            self.Layout()

    def GetResult(self):
        """collect token split result (tuple of strings)"""
        return self.split


class GlossEditButton(wx.Panel):
    """button shows current gloss selection, calls gloss edit dialog when pressed

    Attributes
    ----------
    gloss (Gloss) : currently selected gloss, first item in a list if more than one is selected
    glossstring (str) : string representation of the currently selected gloss
    state (int) : state of the selector

    Widgets
    -------
    button (wx.Button) : button showing gloss information
    """
    def __init__(self, parent, glosslist, statecolours, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.gloss = glosslist[0]
        self.state = None
        self.statecolours = statecolours
        glossstring = makeGlossString(self.CalculateGloss(glosslist), morphemes=True)
        self.button = wx.Button(self, wx.ID_ANY, glossstring, style=wx.NO_BORDER)
        sizer.Add(self.button, 0)
        self.SetSizer(sizer)
        self.button.Bind(wx.EVT_BUTTON, self.OnEditGloss)

    def CalculateGloss(self, glosslist):
        """compute a gloss to be shown on the button as current selection for a list of selections"""
        #print("CalculateGloss glosslist passed:",glosslist)
        def recursiveGlossDigger(gloss):
            if gloss.gloss:
                return gloss.gloss
            else:
                if gloss.morphemes:
                    return u'.'.join([recursiveGlossDigger(g) for g in gloss.morphemes])
            return ''
        form = [v.form for v in glosslist][0]
        ps = tuple(set(itertools.chain(*[v.ps for v in glosslist if v.ps])))
        glosses = []
        for variant in glosslist:
            glosses.append(recursiveGlossDigger(variant))
        if glosses:
            if len(glosses) > 1:
                glosses = glosses[:1] + ['...']
            gloss = u'/'.join(glosses)
        else:
            gloss = ''
        return Gloss(form, ps, gloss, ())

    def OnEditGloss(self, event):
        """show GlossInputDialog when button is pressed"""
        dlg = GlossInputDialog(self, wx.ID_ANY, 'Insérer une glose / Gloss input', size=(600,400), gloss=self.gloss)
        evt = LocaldictLookupEvent(self.GetId(), gloss=self.gloss, dlg=dlg)
        wx.PostEvent(self.GetEventHandler(), evt)
        if (dlg.ShowModal() == wx.ID_OK):
            newgloss = dlg.GetGloss()
            if not newgloss == self.gloss:
                self.gloss = newgloss
                evt = GlossEditEvent(self.GetId(), gloss=newgloss)
                wx.PostEvent(self.GetEventHandler(), evt)
                if dlg.save:
                    evt = LocaldictSaveEvent(self.GetId(), gloss=newgloss)
                    wx.PostEvent(self.GetEventHandler(), evt)
        dlg.Destroy()

    def OnStateChange(self, statecode, gloss):
        """redraw button when state of the selector changes"""
        glossstring = makeGlossString(self.CalculateGloss([gloss]), morphemes=True)
        self.button.SetLabel(glossstring)
        self.Layout()
        try:
            fore, back = self.statecolours[statecode]
            self.button.SetForegroundColour(fore)
            self.button.SetBackgroundColour(back)
            self.SetBackgroundColour(back)
            self.button.Refresh()
            self.Refresh()
            self.state = statecode
        except KeyError:
            #FIXME: proper error message
            print('Unknown state code:', statecode)


class GlossSelector(wx.Panel):
    """group of buttons to select gloss annotation from a list or enter it manually

    Attributes
    ----------
    index (tuple) : token's index in a file (sentence number, token number)
    token (GlossToken) : token object holding initial annotation data
    gloss (Gloss) : selected gloss variant or a first variant in the list if nothing is selected
    form (str) : token string / wordform
    glosslist ([Gloss]) : list of gloss variants (for buttons)
    selectlist ([Gloss]) : list of selected variants (initially empty)
    stage (str) : label indicating source of the token (gdisamb, dparser etc.)
    statecode (int) : selector's state
    Possible values:
                1: 'unambiguous',
                2: 'ambiguous',
                3: 'uncertain',
                4: 'unparsed',
                5: 'manual',
            'selected': 'selected',
            'deselected': 'deselected',
    vertical (bool) : widget orientation

    Widgets
    -------
    tbutton (TokenEditButton) : button for a token
    mbutton (GlossEditButton) : leading button indicating state
    children ([GlossButton]) : gloss variant buttons in a selector
    """
    def __init__(self, parent, index, glosstoken, selectlist, vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.token = glosstoken
        self.toktype, tokvalue = glosstoken.as_tuple()
        if self.toktype == 'w':
            self.form, self.stage, self.glosslist = tokvalue
        else:
            self.form = tokvalue
            self.stage = ''
            self.glosslist = [Gloss(self.form, (self.toktype,), '', ())]
        self.selectlist = selectlist
        self.vertical = vertical
        self.parent = parent
        self.children = []
        self.parserstage = self.stage
        self.index = index

        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(EVT_GLOSS_SELECTED, self.OnGlossSelected)
        self.Bind(EVT_GLOSS_EDITED, self.OnEdition)

        try:
            self.gloss = self.selectlist[0]
        except (IndexError):
            self.gloss = self.glosslist[0]
        self.statecode = self.CalculateState()
        config = wx.Config.Get(False)

        def getforeback(config, name):
            fore = config.Read("colors/{}/fore".format(name))
            back = config.Read("colors/{}/back".format(name))
            return (fore, back)

        self.statecolours = {
                1: getforeback(config, 'unambiguous'),
                2: getforeback(config, 'ambiguous'),
                3: getforeback(config, 'uncertain'),
                4: getforeback(config, 'unparsed'),
                5: getforeback(config, 'manual'),
            'selected': getforeback(config, 'selected'),
            'deselected': getforeback(config, 'deselected'),
                }

        self.tbutton = TokenEditButton(self, self.index, self.toktype, self.form)
        self.mbutton = GlossEditButton(self, self.selectlist or self.glosslist, self.statecolours)

        self.UpdateState(self.statecode, self.gloss)

        if self.vertical:
            self.sizer = wx.BoxSizer(wx.VERTICAL)
        else:
            self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizerflags = (wx.EXPAND | wx.TOP | wx.BOTTOM, 4)
        self.sizer.Add(self.tbutton, 0, *self.sizerflags)
        self.sizer.Add(self.mbutton, 0, *self.sizerflags)
        self.SetSizer(self.sizer)
        self.Layout()

        self.AddButtons(self.glosslist)

        if selectlist:
            for gloss in selectlist:
                for button in self.children:
                    if button.gloss == gloss:
                        button.main.SetValue(True)
                        button.DoToggle()
                else:
                    self.OnSelection(gloss)

    def CalculateState(self):
        """Calculate current state code (self.state)"""
        if len(self.glosslist) > 1:
            statecode = 2
        elif ''.join(self.glosslist[0].ps) in ['', None, '<?>'] and self.glosslist[0].gloss in ['', None, '<?>'] and not self.glosslist[0].morphemes:
            statecode = 4
        else:
            statecode = 1
        return statecode

    def AddButtons(self, glosslist):
        """generate buttons for each variant in a glosslist"""
        # this way, it also generate buttons from localdict for "red" tokens (results of split/joins) with no glosslist
        if self.statecode!=1:
            # JJM add buttons from localdict values here ?
            alreadyAdded=[]
            formlookup=glosslist[0].form
            formlookup=formlookup.lower()   # all indexed in localdict with no tones and lowercase
            metadict=self.GetTopLevelParent().processor.metadata
            if "text:script" in metadict:
                textscript=metadict["text:script"]
            else:
                textscript="Nouvel orthographe malien"
                print("no meta data, assumed text:script= Nouvel orthographe malien")
            if textscript=="Ancien orthographe malien":
                # form is normally parsed in New Orthography - this only handles exception  (where parse failed, notably Proper names)
                formlookup=formlookup.replace("èe","ɛɛ")
                formlookup=formlookup.replace("òo","ɔɔ")
                formlookup=formlookup.replace("è","ɛ")
                formlookup=formlookup.replace("ò","ɔ")   

            savedglosses=[]

            formlookup=re.sub(r'[\u0301\u0300\u0302\u030c]','',formlookup)  # 4 bambara tones
            
            if formlookup in self.GetTopLevelParent().localdict:
                savedglosses = self.GetTopLevelParent().localdict[formlookup]
                #print("AddButtons? - ",len(savedglosses)," for: ",glosslist[0].form,"lookup",formlookup," ->",savedglosses)
                # font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, True)
            # N'ko: essayer aussi en enlevant l'article tonal final (?), ou en l'ajoutant
            elif textscript=="N’Ko" :
                if formlookup[-1]=="`" :
                    formlookup=formlookup[:-1]
                    if formlookup in self.GetTopLevelParent().localdict:
                        savedglosses = self.GetTopLevelParent().localdict[formlookup]
                else:
                    formlookup=formlookup+"`"
                    if formlookup in self.GetTopLevelParent().localdict:
                        savedglosses = self.GetTopLevelParent().localdict[formlookup]

            if len(savedglosses)>0:
                for gloss in savedglosses:
                    if gloss not in alreadyAdded:
                        self.gbutton = GlossButton(self, gloss, self.statecolours,addbylocaldict=True)
                        self.children.append(self.gbutton)
                        self.sizer.Add(self.gbutton, 0, *self.sizerflags)
                        alreadyAdded.append(gloss)            
            # end JJM
        
        if len(self.glosslist) > 1:
            # above JJM code was here in 1st implementation - but red button could not benefit from localdict

            for gloss in glosslist:
                # JJM add : screen already added buttons
                if gloss not in alreadyAdded:
                    gbutton = GlossButton(self, gloss, self.statecolours)
                    self.children.append(gbutton)
                    self.sizer.Add(gbutton, 0, *self.sizerflags)
            self.SetSizer(self.sizer)
            self.Layout()

    def UpdateState(self, statecode, gloss):
        """update leading button's label and color on selector's state change"""
        self.mbutton.OnStateChange(self.statecode, self.gloss)

    def OnEdition(self, evt):
        """update selector buttons when gloss was edited manually by user"""
        gloss = evt.gloss
        self.gloss = gloss
        self.glosslist = [gloss] + [button.gloss for button in self.children]
        for button in self.children:
            if button.selected:
                button.main.SetValue(False)
                button.DoToggle()
        self.selectlist = [gloss]
        self.statecode = 5
        self.UpdateState(self.statecode, self.gloss)
        self.OnSelectorUpdated()
        evt.Skip()

    def OnGlossSelected(self, evt):
        """called when user pressed one of the gloss buttons (FIXME: gloss edits)"""
        gloss = evt.GetEventObject().gloss
        self.OnSelection(gloss)
        self.OnSelectorUpdated()

    def OnSelectorUpdated(self):
        """refresh UI and pass on event on selector update"""
        evt = GlossSelectorEvent(self.GetId())
        evt.SetEventObject(self)
        wx.PostEvent(self.GetEventHandler(), evt)
        self.Layout()

    def OnSelection(self, gloss):
        """update UI and selector's state on a variant selection"""
        if self.children:
            selected = [button.gloss for button in self.children if button.selected]
            for i in self.selectlist:
                if i not in [button.gloss for button in self.children]:
                    selected.insert(0, i)
            self.selectlist = selected
            if len(self.selectlist) > 1:
                self.statecode = 3
                self.gloss = self.selectlist[0]
                self.mbutton.gloss = self.selectlist[0]
                self.stage = 'gdisamb.3'
            elif len(self.selectlist) == 1:
                self.statecode = 5
                self.gloss = self.selectlist[0]
                self.mbutton.gloss = self.selectlist[0]
                self.stage = 'gdisamb.0'
            elif len(self.selectlist) == 0:
                self.statecode = 2
                self.gloss = Gloss(self.children[0].gloss.form, (), '', ())
                self.stage = self.parserstage
            else:
                print("Bug: Negative selection!", selected)
        else:
            self.gloss = gloss
            self.glosslist = [gloss]
            self.selectlist = [gloss]
            self.statecode = 5
            self.stage = 'gdisamb.-1'
        self.UpdateState(self.statecode, self.gloss)

    def GetWordToken(self):
        """generate WordToken from selector's variants"""
        return daba.formats.WordToken(self.glosslist, self.form, self.stage)

    def OnContextMenu(self, evt):
        """context menu shown on right-click on selector's area"""
        if not hasattr(self, "joinfwID"):
            self.joinfwID = wx.NewIdRef(count=1)   # was NewId() JJM
            self.joinbwID = wx.NewIdRef(count=1)   # was NewId()
            self.splitID = wx.NewIdRef(count=1)   # was NewId()
            self.changeID = wx.NewIdRef(count=1)   # was NewId()

        self.Bind(wx.EVT_MENU, self.OnJoinForward, id=self.joinfwID)
        self.Bind(wx.EVT_MENU, self.OnJoinBackward, id=self.joinbwID)
        self.Bind(wx.EVT_MENU, self.OnSplitToken, id=self.splitID)
        self.Bind(wx.EVT_MENU, self.OnChangeTokenType, id=self.changeID)

        menu = wx.Menu()
        menu.Append(-1, "Options for: " + self.form)
        menu.AppendSeparator()
        joinfw = menu.Append(self.joinfwID, "Join with next token")
        joinbw = menu.Append(self.joinbwID, "Join with previous token")
        split = menu.Append(self.splitID, "Split token")
        change = menu.Append(self.changeID, "Change token type (not implemented)")
        # FIXME: not implemented yet
        change.Enable(False)

        # FIXME: lacks elegance, duplicate code, see JoinTwo
        glosses = self.GetTopLevelParent().processor.glosses
        sentpanel = self.GetTopLevelParent().sentpanel
        tokens = glosses[sentpanel.snum].glosslist
        snum, toknum = self.index
        if toknum == 0:
            joinbw.Enable(False)
        elif not tokens[toknum-1].type == 'w':
            joinbw.Enable(False)
        if toknum == len(tokens)-1:
            joinfw.Enable(False)
        elif not tokens[toknum+1].type == 'w':
            joinfw.Enable(False)

        self.PopupMenu(menu)
        menu.Destroy()

    def OnJoinForward(self, evt):
        """generate event to join tokens forward"""
        snum, toknum = self.index
        self.OnJoinTwo(snum, toknum, toknum+1)

    def OnJoinBackward(self, evt):
        """generate event to join tokens backward"""
        snum, toknum = self.index
        self.OnJoinTwo(snum, toknum-1, toknum)

    def OnJoinTwo(self, snum, first, second):
        """post generic event to join a pair of tokens"""
        joinevent = TokenJoinEvent(self.GetId(), snum=snum, first=first, second=second)
        wx.PostEvent(self.GetEventHandler(), joinevent)

    def OnSplitToken(self, evt):
        """get token split point from a user and post token split event"""
        dlg = TokenSplitDialog(self, self.form)
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.GetResult()
            if len(result) > 1:
                splitevent = TokenSplitEvent(self.GetId(), index=self.index, result=result)
                wx.PostEvent(self.GetEventHandler(), splitevent)

    def OnChangeTokenType(self, evt):
        """change token type (not implemented)"""
        pass


class TokenInputDialog(wx.Dialog):
    """dialog to let user edit token and its type"""
    def __init__(self, parent, id, title, tokentype, tokenstr, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)
        self.typedict = dict([("Comment", "Comment"), ("Punctuation", "c"), ("Markup", "Tag"), ("Word", "w")])

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.tokenfield = NormalizedTextCtrl(self, wx.ID_ANY, tokenstr)
        sizer.Add(self.tokenfield)
        self.typefield = wx.RadioBox(self, wx.ID_ANY, "Token type", wx.DefaultPosition, wx.DefaultSize, list(self.typedict.keys()), 1)
        self.typefield.SetStringSelection(dict((v,k) for k,v in self.typedict.items())[tokentype])
        sizer.Add(self.typefield)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)

    def GetToken(self):
        """get token tuple (type, value)"""
        return (self.typedict[self.typefield.GetStringSelection()], self.tokenfield.GetValue())


class SearchDialog(wx.Dialog):
    """search for word and sentence parts"""
    def __init__(self, parent, id, title, searchstr, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.searchfield = NormalizedTextCtrl(self, wx.ID_ANY, searchstr)
        sizer.Add(wx.StaticText(self, wx.ID_ANY, "Search for word or sentence part:"))
        sizer.Add(self.searchfield)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)

    def GetSearchString(self):
        """user's search query"""
        return self.searchfield.GetValue()


class NotFoundDialog(wx.Dialog):
    """dialog showing `Not found` message"""
    def __init__(self, parent, id, title, searchstr, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, -1, u'String "{0}" not found'.format(searchstr)))
        sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)


class StatusColorsDialog(wx.Dialog):
    """dialog to let user select status colors"""
    def __init__(self, parent, config, statuscolors, *args, **kwargs):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, "Select status colors", *args, **kwargs)
        self.config = config
        self.buttonrefs = {}
        sizer = wx.BoxSizer(wx.VERTICAL)
        buttonSizer = wx.FlexGridSizer(5, 7, 2)
        for name, fore, back in statuscolors:
            sampletext = wx.TextCtrl(self, wx.ID_ANY, name)
            sampletext.SetForegroundColour(fore)
            sampletext.SetBackgroundColour(back)
            forebutton = csel.ColourSelect(self, wx.ID_ANY, "", fore)
            backbutton = csel.ColourSelect(self, wx.ID_ANY, "", back)
            forebutton.Bind(csel.EVT_COLOURSELECT, self.OnSelectColor)
            backbutton.Bind(csel.EVT_COLOURSELECT, self.OnSelectColor)
            self.buttonrefs[forebutton.GetId()] = (name.lower(), 'fore', sampletext)
            self.buttonrefs[backbutton.GetId()] = (name.lower(), 'back', sampletext)
            buttonSizer.AddMany([
                (sampletext, 2, wx.EXPAND),
                (wx.StaticText(self, wx.ID_ANY, "Font color: "), 1, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL),
                (forebutton, 1, wx.ALL, 3),
                (wx.StaticText(self, wx.ID_ANY, "Background color: "), 1, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL),
                (backbutton, 1, wx.ALL, 3)
            ])
        sizer.Add(buttonSizer, 0, wx.EXPAND, 4)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)
        self.Layout()
        self.Fit()

    def OnSelectColor(self, evt):
        """write selected color to config file"""
        name, side, sampletext = self.buttonrefs[evt.GetId()]
        colorstring = wx.Colour(*evt.GetValue()).GetAsString(wx.C2S_HTML_SYNTAX)
        self.config.Write("colors/{0}/{1}".format(name, side), colorstring)
        if side == 'fore':
            sampletext.SetForegroundColour(colorstring)
        elif side == 'back':
            sampletext.SetBackgroundColour(colorstring)

        
class TokenEditButton(wx.Panel):
    """button to let user edit token string and type"""
    def __init__(self, parent, index, tokentype, tokenstr, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.index = index
        self.tokenstr = tokenstr
        self.tokentype = tokentype
        self.button = wx.Button(self, wx.ID_ANY, self.tokenstr, style=wx.NO_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.button, 0)
        self.SetSizer(sizer)
        self.button.Bind(wx.EVT_BUTTON, self.OnEditToken)

    def OnEditToken(self, event):
        """collect user's changes to token's type and value, post TokenEditEvent"""
        dlg = TokenInputDialog(self, wx.ID_ANY, 'Edit token', self.tokentype, self.tokenstr)
        if (dlg.ShowModal() == wx.ID_OK):
            self.tokentype, self.tokenstr = dlg.GetToken()
            self.button.SetLabel(self.tokenstr)
            editevent = TokenEditEvent(self.GetId(), index = self.index, toktype=self.tokentype, token=self.tokenstr)
            wx.PostEvent(self.GetEventHandler(), editevent)
        dlg.Destroy()

    def GetToken(self):
        """return token as a tuple (type, value)"""
        return (self.tokentype, self.tokenstr)


class SplitImpossibleDialog(wx.Dialog):
    """dialog showing `Split not possible at this point` message"""
    def __init__(self, parent, id, title, searchstr, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, -1, u'Sentence split point cannot be inside a token'.format(searchstr)))
        sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)


class SentenceText(wx.stc.StyledTextCtrl):
    """colored sentence text widget

    Attributes
    ----------
    token (PlainToken) : sentence token
    text (str) : sentence text
    charspans ([(start, length)]) : list of character spans for each token in a sentence
    intervals (IntervalTree) : button ids corresponding to text spans for each token
    sentpanel (SentPanel) : backref to a perent frame to access its attributes (snum, numsent)
    """
    def __init__(self, parent, *args, **kwargs):
        wx.stc.StyledTextCtrl.__init__(self, parent, *args, **kwargs)
        self.sentpanel = parent
        self.encoder = codecs.getencoder("utf-8")
        self.decoder = codecs.getdecoder("utf-8")
        # defining styles
        config = wx.Config.Get(False)
        self.mainfont = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        savedfont = config.Read("fonts/main")
        if savedfont:
            self.mainfont.SetNativeFontInfoUserDesc(savedfont)
        pb = self.mainfont.GetPointSize() + 2
        face = self.mainfont.GetFaceName()
        self.style_default = 0
        self.style_unambiguous = 1
        self.style_ambiguous = 2
        self.style_uncertain = 3
        self.style_unparsed = 4
        self.style_manual = 5

        self.StyleSetSpec(wx.stc.STC_STYLE_DEFAULT, "size:%d,face:%s,back:#FFFFFF,fore:#1A4780" % (pb, face))
        self.StyleClearAll()
        self.StyleSetSpec(self.style_unambiguous, "size:%d,face:%s,bold,fore:%s,back:%s" % (pb, face, config.Read("colors/unambiguous/fore"), config.Read("colors/unambiguous/back")))
        self.StyleSetSpec(self.style_ambiguous, "size:%d,face:%s,fore:%s,back:%s" % (pb, face, config.Read("colors/ambiguous/fore"), config.Read("colors/ambiguous/back")))
        self.StyleSetSpec(self.style_uncertain, "size:%d,face:%s,fore:%s,back:%s" % (pb, face, config.Read("colors/uncertain/fore"), config.Read("colors/uncertain/back")))
        self.StyleSetSpec(self.style_unparsed, "size:%d,face:%s,fore:%s,back:%s" % (pb, face, config.Read("colors/unparsed/fore"), config.Read("colors/unparsed/back")))
        self.StyleSetSpec(self.style_manual, "size:%d,face:%s,fore:%s,back:%s" % (pb, face, config.Read("colors/manual/fore"), config.Read("colors/manual/back")))
        self.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.Layout()

        self.Bind(wx.EVT_LEFT_UP, self.OnClick)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyPressed)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)

    def calcByteLen(self, text):
        """length of sentence text in bytes"""
        return len(self.encoder(text)[0])

    def calcBytePos (self, text, pos):
        """get byte offset corresponding to a character position in text"""
        return len(self.encoder(text[:pos])[0])

    def calcCharPos(self, bytepos):
        """get character position in a string corresponding to a byte offset"""
        if bytepos == 0:
            return 0
        try:
            return len(self.decoder(self.encoder(self.text)[0][:bytepos])[0])
        except (UnicodeDecodeError):
            self.calcCharPos(self.text, bytepos-1)

    def calcCharSpans(self, tokenbuttons):
        """set spans in text for each token (given a list of token button widgets)"""
        self.charspans = []
        startchar = 0
        charlength = 0
        metadict=self.GetTopLevelParent().processor.metadata  # added JJM 03/10/24
        
        textscript=""
        if "text:script" in metadict:
            textscript=metadict["text:script"]

        for btn in tokenbuttons:
            token = btn.token.token
            charlength = len(token)
            tokenindex = self.text[startchar:].find(token)
            if textscript=="N’Ko":  # FIX THIS (charlength irrelevant)/do not call calcCharSpans for N'ko ?
                tokenindex += startchar
            else:
                if tokenindex == -1:
                    # FIXME: handle missing tokens properly
                    tokenindex = startchar
                    charlength = 0
                    notfound = wx.MessageDialog(self, u'Token not found in the source sentence: ' + token, 'Token not found', wx.OK)
                    notfound.ShowModal()
                    notfound.Destroy()
                else:
                    tokenindex += startchar
            charspan = (tokenindex, charlength)
            startchar = tokenindex+charlength
            self.charspans.append(charspan)
        self.calcButtonIntervals(tokenbuttons, self.charspans)
        return self.charspans

    def calcButtonIntervals(self, tokenbuttons, charspans):
        """assign token button ids to corresponding character intervals in text"""
        self.intervals = IntervalTree()
        for btn, span in zip(tokenbuttons, charspans):
            start, length = span
            if length == 0:
                # FIXME: need to find better solution for the missing tokens
                length = 1
            self.intervals[start:start+length] = btn.GetId()

    def getButtonHere(self, pos):
        """return button id for a given char position"""
        if pos == 0:
            return sorted(self.intervals)[0][2]
        try:
            return sorted(self.intervals[pos])[0][2]
        except (IndexError):
            return self.getButtonHere(pos-1)

    def SetSentence(self, senttoken, tokenbuttons):
        """typeset and color sentence text, attach button ids"""
        self.token = senttoken
        self.text = senttoken.value
        # two fixes (should be fixed elsewhere) - are there more "sentences" ?
        self.GetTopLevelParent().sentpanel.senttext = self.text  # fixed JJM : after token split/join OnCopyToClipboard was returning old sentence
        # now fixed below : if subsequent sentence split, old sentence before after token split/join still there! created havok               
        self.GetTopLevelParent().processor.glosses[self.GetTopLevelParent().sentpanel.snum].senttext = self.text
        #print("SetSentence - processor.glosses[snum]:")
        #sent=self.GetTopLevelParent().processor.glosses[self.GetTopLevelParent().sentpanel.snum]
        #print("SetSentence - glosses... senttext=",sent.senttext)
        #for g in sent.glosslist:
        #    print(str(g))

        self.calcCharSpans(tokenbuttons)
        self.SetText(self.text)
        self.SetReadOnly(True)
        self.StartStyling(0)
        self.SetStyling(self.calcByteLen(self.text), 0)
        self.DoColorSentence(tokenbuttons)

    def ClearSentence(self):
        """clear sentence text widget"""
        self.charspans = []
        self.intervals = IntervalTree()
        self.SetReadOnly(False)
        self.ClearAll()
        
    def DoColorToken(self, btn):
        """color character span corresponding to a token button"""
        snum, toknum = btn.index
        token = btn.token.token
        try:
            startchar, charlength = self.charspans[toknum]
        except (IndexError):
            print(toknum, token)
        bytepos = self.calcBytePos(self.text, startchar)
        bytelen = self.calcByteLen(token)
        self.StartStyling(bytepos)
        self.SetStyling(bytelen, btn.statecode)
        # self.GotoPos(bytepos+bytelen)
        self.Layout()

    def DoColorSentence(self, tokenbuttons):
        """color text spans for each token in a sentence"""
        for btn in tokenbuttons:
            self.DoColorToken(btn)

    def OnSelectorUpdate(self, evt):
        """change token color on selector state change"""
        btn = evt.GetEventObject()
        self.DoColorToken(btn)
        evt.Skip()

    def OnClick(self, evt):
        """post event to move clicked token's selector into view"""
        bytepos = self.GetCurrentPos()
        charpos = self.calcCharPos(bytepos)
        btn_id = self.getButtonHere(charpos)
        btnevt = ShowSelectorEvent(btn_id)
        wx.PostEvent(self.GetEventHandler(), btnevt)
        evt.Skip()

    def OnKeyPressed(self, evt):
        """post event to move the token where Enter key was pressed into view"""
        if evt.GetKeyCode() == wx.stc.STC_KEY_RETURN:
            self.OnClick(evt)
        evt.Skip()
    
    def OnTokenSplit(self, evt):
        """update sentence text after token split"""
        snum, toknum = evt.index
        startchar, charlength = self.charspans[toknum]
        newtokens = u' '.join(evt.result)
        self.UpdateText(startchar, startchar+charlength, newtokens, snum)
        evt.Skip()

    def OnTokenJoin(self, evt):
        """update sentence text after token join"""
        snum = evt.snum
        startfirst, lenfirst = self.charspans[evt.first]
        startsecond, lensecond = self.charspans[evt.second]
        first = self.text[startfirst:startfirst+lenfirst]
        second = self.text[startsecond:startsecond+lensecond]
        self.UpdateText(startfirst, startsecond+lensecond, u''.join((first, second)), snum)
        evt.Skip()

    def OnTokenEdit(self, evt):
        """update sentence text after token edit"""
        snum, toknum = evt.index
        startchar, charlength = self.charspans[toknum]
        senttoken = self.text[startchar:startchar+charlength]
        if not senttoken == evt.token:
            self.UpdateText(startchar, startchar+charlength, evt.token, snum)
        evt.Skip()

    def UpdateText(self, start, end, newtext, snum):
        """replace characters between start and end with newtext, update colors and button bindings"""
        self.text = ''.join([self.text[:start], newtext, self.text[end:]])
        self.token.value = self.text
        #print("UpdateText self.token.value",self.token.value)
        #print("UpdateText self.token",self.token)
        sentevent = SentenceEditEvent(self.GetId(), snum=snum, sent=self.token)
        wx.PostEvent(self.GetEventHandler(), sentevent)

    def Highlight(self, start, end):
        """highlight characters between start and end (not implemented)"""
        pass

    def OnContextMenu(self, evt):
        """pop-up sentence context menu on right-click"""
        if not hasattr(self, "joinfwID"):
            self.splitID = wx.NewIdRef(count=1)   # was NewId()    JJM
            self.joinfwID = wx.NewIdRef(count=1)   # was NewId()
            self.joinbwID = wx.NewIdRef(count=1)   # was NewId()

        self.Bind(wx.EVT_MENU, self.OnJoinForward, id=self.joinfwID)
        self.Bind(wx.EVT_MENU, self.OnJoinBackward, id=self.joinbwID)
        self.Bind(wx.EVT_MENU, self.OnSplitSentence, id=self.splitID)

        menu = wx.Menu()
        menu.Append(-1, "Options for this sentence: ")
        menu.AppendSeparator()
        menu.Append(self.splitID, "Split sentence at this point")
        joinfw = menu.Append(self.joinfwID, "Join with next sentence")
        joinbw = menu.Append(self.joinbwID, "Join with previous sentence")

        if self.sentpanel.snum == 0:
            joinbw.Enable(False)
        elif self.sentpanel.snum == self.sentpanel.numsent:
            joinfw.Enable(False)

        self.PopupMenu(menu)
        menu.Destroy()

    def OnJoinForward(self, evt):
        """generate event to join sentences forward"""
        snum = self.sentpanel.snum
        self.OnJoinSentences(snum, snum+1)

    def OnJoinBackward(self, evt):
        """generate event to join sentences backward"""
        snum = self.sentpanel.snum
        self.OnJoinSentences(snum-1, snum)

    def OnJoinSentences(self, first, second):
        """post event to join two sentences"""
        sjoinevent = SentenceJoinEvent(self.GetId(), first=first, second=second)
        wx.PostEvent(self.GetEventHandler(), sjoinevent)

    def OnSplitSentence(self, evt):
        """split sentence at the cursor point"""
        bytepos = self.GetCurrentPos()
        charpos = self.calcCharPos(bytepos)
        last = len(self.text)
        #print("OnSplitSentence - text:",self.text)
        if charpos < last:
            first = self.intervals.overlap(0, charpos)
            tnum = len(first)
            if self.intervals[charpos]:
                charpos = charpos-1
                if self.intervals[charpos]:
                    #print("OnSplitSentence -impossible- intervals[charpos]=",self.intervals[charpos])
                    # On ne peut splitter qu'entre deux "boutons": pas de boutons pour les ponctuations et les Tags... dommage!
                    self.SplitImpossibleError(evt)
                    return
            # make sure that both parts contain tokens
            if tnum > 0 and tnum < len(self.charspans):
                snum = self.sentpanel.snum
                ssplitevent = SentenceSplitEvent(self.GetId(), snum=snum, tnum=tnum, charpos=charpos)
                wx.PostEvent(self.GetEventHandler(), ssplitevent)
            else:
                #print("OnSplitSentence -impossible- tnum, len(charspan)",tnum,len(self.charspans))
                self.SplitImpossibleError(evt)

    def SplitImpossibleError(self, e):
        """sentence split at this point not possible error message"""
        dlg = wx.MessageDialog(self,
                               """Impossible to split sentence at this point.
 
    Sentence split point cannot be inside a token
    or at the very beginning and end of sentence.
    Please position split point between tokens
    and try again""",
                               'Impossible to split sentence at this point',
                               wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

class SentAttributes(wx.Panel):
    """sentence-level attributes widget
    
    Attrbutes
    ---------
    attrs (dict) : name—value mapping for attributes
    """
    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.attrs = {}
        self.fields = {}
        self.delbuttons = {}
        self.snum = None
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.newkey = wx.TextCtrl(self, wx.ID_ANY, '')
        self.addbutton = wx.Button(self, wx.ID_ANY, 'Add attribute', style=wx.NO_BORDER)
        self.addbutton.Bind(wx.EVT_BUTTON, self.OnAddAttribute)
        hbox.Add(self.newkey, 0)
        hbox.Add(self.addbutton, 0)
        self.sizer.Add(hbox)
        self.attribSizer = wx.FlexGridSizer(3, 1, 1)
        self.attribSizer.AddGrowableCol(1)
        self.sizer.Add(self.attribSizer, 1, wx.EXPAND)
        self.SetSizer(self.sizer)
        self.Layout()

    def SetSentence(self, senttoken, snum):
        """show widgets for sentence-level attributes if present in a sentence"""
        self.snum = snum
        if senttoken.attrs:
            alist = senttoken.attrs.items()
            #alist.sort() # no longer works in Python 3
            alist=sorted(alist)  # mod JJM 6/11/24
            for keytext, value in alist:
                key = wx.StaticText(self, wx.ID_ANY, keytext)
                field = wx.TextCtrl(self, wx.ID_ANY, value)
                field.Bind(wx.EVT_TEXT, self.OnEditValue)
                delbutton = wx.Button(self, wx.ID_ANY, style=wx.BU_EXACTFIT | wx.BU_NOTEXT)
                #delbutton.SetBitmapLabel(wx.ArtProvider.GetBitmap(wx.ART_DELETE | wx.ART_MENU))
                delbutton.SetBitmapLabel(wx.ArtProvider.GetBitmap(wx.ART_DELETE))  # JJM 6/11/24
                delbutton.Bind(wx.EVT_BUTTON, self.OnDeleteAttribute)
                self.fields[keytext] = field
                self.attrs[keytext] = value
                self.delbuttons[delbutton.GetId()] = (keytext, key, field, delbutton)
                self.attribSizer.AddMany([
                    (key, 1, wx.EXPAND),
                    (field, 10, wx.EXPAND),
                    (delbutton, 0)
                ])
            self.attribSizer.Layout()
            self.Layout()
            self.Fit()

    def OnEditValue(self, evt):
        """update attribute values on user input"""
        attrs = {}
        for key, field in self.fields.items():
            attrs[key] = field.GetValue()
        self.attrs = attrs
        sattrsevent = SentAttrsEditEvent(self.GetId(), snum=self.snum, attrs=self.attrs)
        wx.PostEvent(self.GetEventHandler(), sattrsevent)

    def OnAddAttribute(self, evt):
        """create widgets for a new attribute"""
        keytext = self.newkey.GetValue()
        key = wx.StaticText(self, wx.ID_ANY, keytext)
        value = wx.TextCtrl(self, wx.ID_ANY, '')
        delbutton = wx.Button(self, wx.ID_ANY, style=wx.BU_EXACTFIT | wx.BU_NOTEXT)
        delbutton.SetBitmapLabel(wx.ArtProvider.GetBitmap(wx.ART_DELETE, wx.ART_MENU))
        self.fields[keytext] = value
        self.delbuttons[delbutton.GetId()] = (keytext, key, value, delbutton)
        value.Bind(wx.EVT_TEXT, self.OnEditValue)
        delbutton.Bind(wx.EVT_BUTTON, self.OnDeleteAttribute)
        self.attribSizer.AddMany([
            (key, 1, wx.EXPAND),
            (value, 10, wx.EXPAND),
            (delbutton, 0, wx.EXPAND)
        ])
        self.attribSizer.Layout()
        self.GetParent().Layout()

    def OnDeleteAttribute(self, evt):
        """remove widgets on attribute deletion"""
        btn_id = evt.GetId()
        keytext, key, value, delbutton  = self.delbuttons[btn_id]
        for w in (key, value, delbutton):
            item = self.attribSizer.GetItem(w)
            item.DeleteWindows()
        self.attribSizer.Layout()
        del self.attrs[keytext]
        del self.fields[keytext]
        del self.delbuttons[btn_id]

    def ClearSentence(self):
        """clear attribute data and widgets on sentence switch"""
        self.attrs = {}
        self.fields = {}
        self.delbuttons = {}
        self.snum = None
        self.attribSizer.Clear(delete_windows=True)


# PANELS


class FilePanel(wx.ScrolledWindow):
    """Text fileview panel"""
    def __init__(self, parent, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.parent = parent
        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.isFileShown=False
        self.st = SentText(self, -1, num=-1, style=wx.ST_NO_AUTORESIZE)

    def ShowFile(self, sentlist):
        """show source text for a file"""

        if self.isFileShown:
            # print("ShowFile : Clear & Remove")
            self.Sizer.Clear(delete_windows=True)   # that's the key element missing : delete_windows=True
            self.Sizer.Remove(self.Sizer)   # proably does not do a thing...

        # added JJM : load html file & html sentences and gloss
        #fileIN = open(os.path.join(self.GetTopLevelParent().dirname, self.GetTopLevelParent().filename), "r") # OK on Unix, not windows
        fileIN=codecs.open(os.path.join(self.GetTopLevelParent().dirname, self.GetTopLevelParent().filename), 'r', encoding="UTF-8")
        htmlfile=fileIN.read()
        fileIN.close()
        htmlfile=re.sub(r"\r\n","\n",htmlfile,0,re.U|re.MULTILINE)  # takes care of windows line endings?

        head,body=htmlfile.split("<body>")
        # old format ?
        # check if body has strange sentence ending sequence
        body=re.sub(r'\n</span></span>\n</span>','\n</span>\n</span>\n</span>',body,0,re.U|re.MULTILINE)

        if '</span><span class="w"' in body or '</span><span class="c"' in body:
            # print("adapting file to new html format")
            body,nadapt=re.subn(r'\n</span><span class="(w|c|t)"',r'</span>\n<span class="\g<1>"',body,0,re.U|re.MULTILINE)

        body=body[:-18]
        
        sentences=body.split("</span>\n</span>\n</span>\n")

        #Sizer = wx.BoxSizer(wx.VERTICAL)
        for n, senttoken in enumerate(sentlist):
            self.st = SentText(self, -1, num=n, style=wx.ST_NO_AUTORESIZE)
            stv=senttoken.value   # JJM : stv and stv handling - add marker for ambiguity in sentence
            stv=re.sub(r'\n','␤',stv)
            stv=str(n+1)+". "+stv
            padleft="\t \t"

            # broken html structures may break here
            try:
                if "lemma var" in sentences[n]: padleft="\t*\t"
            except IndexError:
                pass

            stv=padleft+stv
            self.st.SetLabel(stv)
            #st.SetLabel(senttoken.value)
            self.st.Wrap(self.GetClientSize().GetWidth()-20)
            self.st.Bind(wx.EVT_LEFT_DOWN, self.st.onMouseEvent)
            #Sizer.Add(st, 1, wx.EXPAND)
            self.Sizer.Add(self.st, 1, wx.EXPAND)

        #self.SetSizer(Sizer)
        self.SetSizer(self.Sizer)
        self.Layout()
        self.isFileShown=True

class MetaPanel(wx.ScrolledWindow):
    def __init__(self, parent, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.parent = parent
        self.isMetaShown=False
        self.Sizer = wx.BoxSizer(wx.VERTICAL)

    def ShowMetas(self, metadata):

        if self.isMetaShown:
            self.Sizer.Clear(delete_windows=True)   # that's the key element missing : delete_windows=True
            self.Sizer.Remove(self.Sizer)   # probably does not do a thing...

        metas={}
        items=[]
        authors=False
        for x,y in metadata.items():
          item,subitem=x.split(":")
          if item=="author":
            if subitem=="name": subitem="_name" # force sorting as 1st
          elif item in ["source","text"] :
            if subitem=="title": subitem="_title"
            
          if item in items:
            if item=="author" and authors:
              vy=y.split("|")
              authindex=0
              for v in vy:
                authindex+=1
                metas[item][authindex][subitem]=v
            else:
              metas[item][subitem]=y
          else: 
            items.append(item)
            if item=="author":
              if "|" in y:
                vy=y.split("|")
                authors=True
                authindex=0
                for v in vy:
                  authindex+=1
                  if authindex==1: 
                          metas[item]={authindex: {subitem:v}}
                  else :  metas[item][authindex]={subitem:v}
              else:
                metas[item]={subitem:y}
              #print("\n",metas,"\n")
            else:
              metas[item]={subitem:y}
        
        # print sorted metas
        metatxt="\n"
        for x,y in sorted(metas.items()):
          metatxt+=x+"\n"
          for w,z in sorted(y.items()):
            if x=="author" and authors:
              metatxt+="\t"+str(w)+"\n"
              for wn,zn in sorted(z.items()):
                metatxt+="\t\t"+wn.strip("_")+" :\t "+zn+"\n"
            else: 
                metatxt+="\t"+w.strip("_")+" :\t "+z+"\n"
        metatxt=metatxt.replace("\n","\n   ")

        self.st= wx.TextCtrl(self,style=wx.TE_MULTILINE|wx.TE_DONTWRAP)
        self.st.SetValue(metatxt)
        #font = wx.Font(12, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        #self.SetFont(font)
        self.metafont = self.GetFont()
        self.metafont.SetPointSize(self.metafont.GetPointSize() + 2)
        self.st.SetFont(self.metafont)
        self.Sizer.Add(self.st, 1, wx.EXPAND)        

        self.SetSizer(self.Sizer)
        self.Layout()
        self.isMetaShown=True     

class DictPanel(wx.ScrolledWindow):
    def __init__(self, parent, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.parent = parent
        self.isDictShown=False
        self.Sizer = wx.BoxSizer(wx.VERTICAL)

    def ShowDict(self,localdictfile):
        global ldtext
        if self.isDictShown:
            # print("ShowDict : Clear & Remove")
            self.Sizer.Clear(delete_windows=True)   # that's the key element missing : delete_windows=True
            self.Sizer.Remove(self.Sizer)   # probably does not do a thing...

        if os.path.exists(localdictfile):
            #ldfile=open(localdictfile,'r')  # OK only on UNix
            ldfile=codecs.open(localdictfile, 'r', encoding="UTF-8")
            ldtext=ldfile.read()
            ldtext=re.sub(r"\r\n","\n",ldtext,0,re.U|re.MULTILINE)  # takes care of windows line endings?
            ldfile.close()
        else : ldtext="vous n'avez pas de localdict pour l'instant"
        self.ldfile=localdictfile
       
        centeredLabel = wx.StaticText(self, -1, localdictfile)
        self.Sizer.Add(centeredLabel, flag=wx.ALIGN_CENTER_HORIZONTAL)
        self.st= wx.TextCtrl(self,style=wx.TE_MULTILINE)
        self.st.SetValue(ldtext)
        self.Sizer.Add(self.st, 1, wx.EXPAND)
        submitButton = wx.Button(self, wx.ID_SAVE,'Save')
        submitButton.Bind(wx.EVT_BUTTON, self.OnSave)
        self.Sizer.Add(submitButton,0,wx.ALIGN_CENTER)
        self.SetSizer(self.Sizer)
        self.Layout()
        self.isDictShown=True

    def OnSave(self,e):
        ldfile=codecs.open(self.ldfile, 'w', encoding="UTF-8")
        ldtext=self.st.GetValue()
        ldfile.write(ldtext)
        ldfile.close()
        self.GetTopLevelParent().SetLocaldict(self.ldfile)
        

class SentPanel(wx.Panel):
    """Manual disambiguation panel

    Attributes
    ----------
    snum (int) : sentence index
    numsent (int) : total number of sentences in a file
    senttoken () : sentence token
    selectlist () : list of selected glosses
    tokenlist () : list of token objects
    sentindex () : index of a sentence
    senttext () : sentence text

    savedstate (bool) : 
    isshown (bool) : sentence is loaded, widgets shown

    Widgets
    -------
    sentnumbutton (wx.SpinCtrl) : choose sentence by number
    searchbutton (wx.SearchCtrl) : search query input field
    findprevbutton : find previous
    findnextbutton : find next
    nextambigbutton : jump to next sentence with ambiguous words
    navsizer : navigation sizer
    sentsource (SentenceText) : sentence text widget
    sentattrs (SentAttributes) : sentence-level attributes panel
    annotlist (ScrolledPanel) : token annotation buttons
    """
    def __init__(self, parent, vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.vertical = vertical
        self.savedstate = None
        self.isshown = False
        self.snum = 0
        self.numsent = self.GetTopLevelParent().processor.numsent
        self.sentfont = self.GetFont()
        self.sentfont.SetPointSize(self.sentfont.GetPointSize() + 2)
        self.sentcolor = 'Navy'

        # create navigation buttons
        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.sentnumbutton = wx.SpinCtrl(self, wx.ID_ANY, "",
                                         (10, 20), style=wx.TE_PROCESS_ENTER)
        self.sentnumbutton.SetRange(1, self.numsent)
        prevbutton = wx.Button(self, wx.ID_ANY, '<')
        prevbutton.Bind(wx.EVT_BUTTON, self.PrevSentence)
        nextbutton = wx.Button(self, wx.ID_ANY, '>')
        nextbutton.Bind(wx.EVT_BUTTON, self.NextSentence)
        savebutton = wx.Button(self, wx.ID_ANY, 'Save results')
        savebutton.Bind(wx.EVT_BUTTON, self.OnSaveResults)
        self.searchbutton = wx.SearchCtrl(self, size=(200, -1), style=wx.TE_PROCESS_ENTER)
        self.findprevbutton = wx.Button(self, wx.ID_ANY, '←ꙭ')
        self.findnextbutton = wx.Button(self, wx.ID_ANY, 'ꙭ→')
        self.nextambigbutton = wx.Button(self, wx.ID_ANY, '???►►')
        self.navsizer = wx.BoxSizer(wx.HORIZONTAL)
        sentenceno = wx.StaticText(self, wx.ID_ANY, "Sentence No")
        sentenceno.SetFont(self.sentfont)
        sentenceno.SetForegroundColour(self.sentcolor)
        self.navsizer.Add(sentenceno, 0)
        self.navsizer.Add(self.sentnumbutton)
        self.sentof = wx.StaticText(self, wx.ID_ANY, " of {}  ".format(self.numsent))
        self.sentof.SetFont(self.sentfont)
        self.sentof.SetForegroundColour(self.sentcolor)
        self.navsizer.Add(self.sentof, 0)
        self.navsizer.Add(prevbutton, 0)
        self.navsizer.Add(nextbutton, 0)
        self.navsizer.Add(self.nextambigbutton, 0)
        self.navsizer.Add(savebutton, 0)
        self.navsizer.Add(self.searchbutton, 0, wx.EXPAND)
        self.navsizer.Add(self.findprevbutton, 0)
        self.navsizer.Add(self.findnextbutton, 0)
        copybutton = wx.Button(self, wx.ID_COPY)
        copybutton.Bind(wx.EVT_BUTTON, self.OnCopyToClipboard)
        self.navsizer.Add(copybutton)
        copybutton2 = wx.Button(self, wx.ID_ANY, "Copy2")
        copybutton2.Bind(wx.EVT_BUTTON, self.OnCopyToClipboard2)
        self.navsizer.Add(copybutton2)
        copybuttonrepl = wx.Button(self, wx.ID_ANY, "Copyrepl")   # added 14/nov/2024
        copybuttonrepl.Bind(wx.EVT_BUTTON, self.OnCopyToClipboardRepl)
        self.navsizer.Add(copybuttonrepl)
        self.sentsource = SentenceText(self)
        self.sentattrs = SentAttributes(self)
        self.Sizer.Add(self.navsizer)
        self.Sizer.Add(self.sentsource, 0, wx.EXPAND)
        self.Sizer.Add(self.sentattrs, 0, wx.EXPAND) # reset by JJM 6/nov/24
        self.SetSizer(self.Sizer)
        self.Layout()

        # bind custom events
        self.Bind(EVT_SELECTOR_UPDATED, self.OnSelectorUpdate)
        self.Bind(EVT_SHOW_SELECTOR, self.OnShowSelector)
        self.Bind(EVT_TOKEN_EDIT, self.sentsource.OnTokenEdit)
        self.Bind(EVT_TOKEN_JOIN, self.sentsource.OnTokenJoin)
        self.Bind(EVT_TOKEN_SPLIT, self.sentsource.OnTokenSplit)
        self.Bind(EVT_SENTENCE_JOIN, self.OnSentenceJoin)
        self.Bind(EVT_SENTENCE_SPLIT, self.OnSentenceSplit)

    def CreateGlossButtons(self):
        """generate GlossSelector widgets for each token in a sentence"""
        tokenbuttons = []
        self.annotlist = wx.lib.scrolledpanel.ScrolledPanel(self, wx.ID_ANY)
        self.annotlist.SetScrollRate(20, 20)
        self.annotlist.SetBackgroundColour((236, 211, 211, 255)) # was (60, 25, 25, 25)
        if self.vertical:
            annotsizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            annotsizer = wx.BoxSizer(wx.VERTICAL) 
        for (toknum, (token, selectlist)) in enumerate(zip(self.tokenlist, self.selectlist)):
            abox = GlossSelector(self.annotlist, (self.snum, toknum), token, selectlist, vertical=self.vertical)
            tokenbuttons.append(abox)
            annotsizer.Add(abox)
        self.annotlist.SetSizer(annotsizer)
        self.annotlist.Layout()
        return tokenbuttons

    def ShowSent(self, sentannot):
        """set sentence data attributes and show widgets"""
        self.senttoken, self.selectlist, self.tokenlist, self.sentindex = sentannot.as_tuple()
        self.senttext = sentannot.senttext.strip()
        #print ("ShowSent *** sentannot :",sentannot)
        """
        print ("*** self.senttoken :",self.senttoken)
        print ("*** self.selectlist :",self.selectlist)
        #print ("*** self.tokenlist :",self.tokenlist)
        print ("*** self.sentindex :", self.sentindex)
        print ("self.senttext :",self.senttext)
        print ("self.isshown :",self.isshown)
        """

        if self.isshown:
            self.sentsource.ClearSentence()
            self.sentattrs.ClearSentence()
            self.Sizer.Remove(self.annotlist.GetSizer())
            self.annotlist.Destroy()
        
        self.snum = sentannot.snum
        self.sentnumbutton.SetValue(self.snum+1)
        tokenbuttons = self.CreateGlossButtons()
        self.sentsource.SetSentence(self.senttoken, tokenbuttons)
        self.sentattrs.SetSentence(self.senttoken, self.snum)
        self.Sizer.Add(self.annotlist, 1, wx.EXPAND)
        self.Layout()
        self.isshown = True

    def PrevSentence(self, event):
        """show previous sentence"""
        self.OnSaveResults(event)
        if self.snum > 0:
            prevsent = self.snum-1
        else:
            prevsent = len(self.GetTopLevelParent().processor.glosses)-1
        self.GetTopLevelParent().ShowSent(prevsent)

    def NextSentence(self, event):
        """show next sentence"""
        self.OnSaveResults(event)
        nextsent = self.snum+1
        try:
            self.GetTopLevelParent().ShowSent(nextsent)
        except IndexError:
            self.GetTopLevelParent().ShowSent(0)

    def OnSaveResults(self, event):
        """post event to save results"""
        evt = SaveResultsEvent(self.GetId())
        wx.PostEvent(self.GetEventHandler(), evt)

    def OnCopyToClipboard(self, evt):
        """copy sentence text to a clipboard"""
        if self.senttext:
            clipdata = wx.TextDataObject()
            clipdata.SetText(self.senttext)
            if not wx.TheClipboard.IsOpened():
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(clipdata)
                wx.TheClipboard.Close()

    def OnCopyToClipboard2(self, evt):
        """copy sentence text to a clipboard"""
        global copy2spacer
        if self.senttext:
            clipdata2 = wx.TextDataObject()
            #clipdata2.SetText(self.senttext) - build it from ligne2
            l2orig=""
            l2lx=""
            l2ps=""
            l2gloss=""
            #print("OnCopyToClipboard2: CHECK toknum, (token, selectlist):\n")
            glosses = self.GetTopLevelParent().processor.glosses
            sent= glosses[self.snum]
            # is there a way to generate table only for selected text ???
            # try to get selection
            #  frm, to = sent.GetSelection()  # AttributeError: 'SentAnnot' object has no attribute 'GetSelection'
            # frm, to = self.sentsource.GetSelection()
            # myselection=self.sentsource.GetStringSelection()
            myselectedtext=self.sentsource.GetSelectedText()
            myselectedtext=myselectedtext.strip()
            myselectedtext=myselectedtext.replace('\u07f8', ",")  # N'Ko COMMA - as done in line 2
            myselectedtext=myselectedtext.replace('\u060c', ",")  # Arabic comma
            myselectedtext=myselectedtext.replace(' , ', ", ")
            myselectedtext=myselectedtext.replace('\u061f', "?")  # Arabic question mark
            myselectedtext=myselectedtext.replace('؛', r":")           # U+061B ؛ ARABIC SEMICOLON
            myselectedtext=myselectedtext.replace('\u066a', "%")  # Arabic Percent sign ٪
            myselectedtext=myselectedtext.replace('\u07f9', "!")  # N'Ko EXLAMATION MARK
            # selstart=self.sentsource.GetSelectionStart()   # same values as frm,to
            # selend=self.sentsource.GetSelectionEnd()
            # print("GetSelection: frm,to=",frm,to)
            # print("selstart, selend=",selstart, selend)
            # frm=int(frm/2)   # these values seem erratic and unusable!!!
            # to=int(to/2)
            # rem ; senttext =? sentsource.text - no:  sentsource.text should be used, but still, results are impredictable
            # print('senttext="'+self.senttext+'"')
            # print('sentsource.text="'+self.sentsource.text+'"')
            # print("GetSelection:self.senttext[",frm,":",to,"]=",self.senttext[frm:to])
            # print("GetSelection:self.sentsource.text[",frm,":",to,"]=",self.sentsource.text[frm:to])
            # print("GetStringSelection:myselection",myselection) # same as above
            #print("GetSelectedText:myselectedtext",myselectedtext)  # results OK but position in sentence is unknown- can only select 1st occurrence
            # tried and failed with encoder/decoder
            # print(self.sentsource.charspans)   # how did they get this right ? ah, they don't use mouse selections!
            # end try 
            # print("sent.glosslist=",sent.glosslist)
            mysentlist=[]
            for w in sent.glosslist:
                mysentlist.append(w.token)
            """
            print("senttoken=",self.senttoken)
            print("senttoken.value=",self.senttoken.value)
            #mytoks=enumerate(zip(self.senttoken))
            #print("mytoks=",mytoks)
            print("senttext=",self.senttext)
            mysent=self.senttext   # need a better way!!!?? ?????????????
            #  this approach fails in case of split / join
            #mysent=self.senttoken.value
            #mysent=mysent.strip()
            mysent=mysent.replace("ߵ","ߵ ")
            mysent=mysent.replace("."," .")
            mysent=mysent.replace('\u07f8', " \u07f8")  # N'Ko COMMA
            mysent=mysent.replace('\u060c', " \u060c")  # Arabic comma
            mysent=mysent.replace('\u061f', " \u061f")  # Arabic question mark
            mysent=mysent.replace('؛', r" ؛")           # U+061B ؛ ARABIC SEMICOLON
            mysent=mysent.replace('\u07fa', " \u07fa")  # N'KO LAJANYALAN
            mysent=mysent.replace('\u066a', " \u066a")  # Arabic Percent sign ٪
            mysent=mysent.replace('\u07f9', " \u07f9")  # N'Ko EXLAMATION MARK
            mysent=mysent.replace('\n', " ")          # Newline side-effects
            while "  " in mysent:
                mysent=mysent.replace("  "," ")
            mysent=mysent.strip()
            mysentlist=mysent.split(" ")
            """
            mysentlistselected=""
            for (toknum, (token, selectlist)) in enumerate(zip(self.tokenlist, self.selectlist)):
                if selectlist: 
                    mytokenlist=selectlist
                else: 
                    mytokenlist=token.glosslist
                mytoken=mytokenlist[0]
                # print("mytoken:", mytoken)
                if myselectedtext!="":
                    if mysentlistselected=="":  mysentlistselected=mysentlistselected+mysentlist[toknum]
                    else:
                        if mytoken.gloss=="c" or mysentlistselected[-1] in ["'","’","ߴ","ߵ"]:  # added N'ko apostrophes (high & low tone)
                                                mysentlistselected=mysentlistselected+mysentlist[toknum]
                        else:                   mysentlistselected=mysentlistselected+" "+mysentlist[toknum]
                    # print("mysentlistselected:",mysentlistselected)
                    # CAUTION this only handles some punctuations !!!
                    if not myselectedtext.startswith(mysentlistselected) : 
                        mysentlistselected=""  # wrong sequence, start over again - Note this will only get the first occurrence of a selected sequence!
                        l2orig=""
                        l2lx=""
                        l2ps=""
                        l2gloss=""
                        continue
                mylx=mytoken.form
                myps="/".join(mytoken.ps)
                mygloss=mytoken.gloss
                if mygloss==None: mygloss=""
                if mygloss=="" :
                    for mymorph in mytoken.morphemes:
                        if mymorph.gloss!=None: mygloss+=mymorph.gloss+"_"
                    mygloss=mygloss[:-1]
                l2orig=l2orig+mysentlist[toknum]+copy2spacer
                l2lx+=mylx+copy2spacer
                l2ps+=myps+copy2spacer
                #print("mygloss:",mygloss)
                l2gloss+=mygloss+copy2spacer
                if myselectedtext!="":
                    if mysentlistselected==myselectedtext: break
            if myselectedtext!="" and mysentlistselected=="": clipdata2.SetText("Sorry, couln't find "+myselectedtext)
            else: clipdata2.SetText(l2orig[:-1]+"\n"+l2lx[:-1]+"\n"+l2ps[:-1]+"\n"+l2gloss[:-1])
            if not wx.TheClipboard.IsOpened():
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(clipdata2)
                wx.TheClipboard.Close()

    def OnCopyToClipboardRepl(self, evt):
        """copy sentence text to a clipboard"""
        metadict=self.GetTopLevelParent().processor.metadata
        if "text:script" in metadict:
            textscript=metadict["text:script"]
            if textscript=="": textscript="Nouvel orthographe malien" # default
        else: textscript="Nouvel orthographe malien" # default
        if self.senttext:
            clipdata2 = wx.TextDataObject()
            l2orig=""
            l2token=""
            glosses = self.GetTopLevelParent().processor.glosses
            sent= glosses[self.snum]
            myselectedtext=self.sentsource.GetSelectedText()
            myselectedtext=myselectedtext.strip()
            if textscript=="N’Ko":
                myselectedtext=myselectedtext.replace('\u07f8', ",")  # N'Ko COMMA - as done in line 2
                myselectedtext=myselectedtext.replace('\u060c', ",")  # Arabic comma
                myselectedtext=myselectedtext.replace(' , ', ", ")
                myselectedtext=myselectedtext.replace('\u061f', "?")  # Arabic question mark
                myselectedtext=myselectedtext.replace('؛', r":")           # U+061B ؛ ARABIC SEMICOLON
                myselectedtext=myselectedtext.replace('\u066a', "%")  # Arabic Percent sign ٪
                myselectedtext=myselectedtext.replace('\u07f9', "!")  # N'Ko EXLAMATION MARK
            #print("GetSelectedText:myselectedtext",myselectedtext)  # results OK but position in sentence is unknown- can only select 1st occurrence
            mysentlist=[]
            for w in sent.glosslist:
                mysentlist.append(w.token)
            mysentlistselected=""
            for (toknum, (token, selectlist)) in enumerate(zip(self.tokenlist, self.selectlist)):
                if selectlist: 
                    mytokenlist=selectlist
                else: 
                    mytokenlist=token.glosslist
                mytoken=mytokenlist[0]
                # print("mytoken:", mytoken)
                if myselectedtext!="":
                    if mysentlistselected=="":  mysentlistselected=mysentlistselected+mysentlist[toknum]
                    else:
                        if mytoken.gloss=="c" or mysentlistselected[-1] in ["'","’","ߴ","ߵ"]:  # added N'ko apostrophes (high & low tone)
                                                mysentlistselected=mysentlistselected+mysentlist[toknum]
                        else:                   mysentlistselected=mysentlistselected+" "+mysentlist[toknum]
                    # print("mysentlistselected:",mysentlistselected)
                    # CAUTION this only handles some punctuations !!!
                    if not myselectedtext.startswith(mysentlistselected) : 
                        mysentlistselected=""  # wrong sequence, start over again - Note this will only get the first occurrence of a selected sequence!
                        l2orig=""
                        l2token=""
                        continue
                if textscript=="N’Ko":
                    l2orig+=mysentlist[toknum]+"_"
                else:
                    l2orig+=mytoken.form+"_"
                l2token+=str(mytoken)+"_"
                if myselectedtext!="":
                    if mysentlistselected==myselectedtext: break
            if myselectedtext!="" and mysentlistselected=="": 
                clipdata2.SetText("Sorry, couln't find "+myselectedtext)
            else: 
                l2orig=l2orig.replace(",","COMMA")
                l2token=l2token.replace(",::c","COMMA")
                clipdata2.SetText(l2orig[:-1]+"==="+l2token[:-1])
            if not wx.TheClipboard.IsOpened():
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(clipdata2)
                wx.TheClipboard.Close()

    def OnSelectorUpdate(self, evt):
        """pass selector update event to the sentence text widget"""
        self.sentsource.OnSelectorUpdate(evt)
        self.Layout()
        evt.Skip()

    def OnShowSelector(self, evt):
        """move requested gloss selector into view"""
        btn_id = evt.GetId()
        btn = self.annotlist.FindWindowById(btn_id)
        self.annotlist.ScrollChildIntoView(btn)

    def UpdateNumsent(self, numsent):
        """update numsent value and its display"""
        self.numsent = numsent
        self.sentnumbutton.SetRange(1, self.numsent)
        self.navsizer.Detach(self.sentof)
        self.sentof.Show(False)
        self.sentof = wx.StaticText(self, wx.ID_ANY, " of {}  ".format(self.numsent))
        self.sentof.SetFont(self.sentfont)
        self.sentof.SetForegroundColour(self.sentcolor)
        self.navsizer.Insert(2, self.sentof)
        self.navsizer.Show(2)
        self.navsizer.Layout()
        
    def OnSentenceJoin(self, evt):
        """update UI and data due to sentence join"""
        self.UpdateNumsent(self.numsent-1)
        evt.Skip()

    def OnSentenceSplit(self, evt):
        """update UI and data due to sentence split"""
        self.UpdateNumsent(self.numsent+1)
        evt.Skip()


class MainFrame(wx.Frame):
    """Main frame

    Attributes
    ----------
    config (wx.Config) : configuration data
    dirname (str) : saved working directory
    infile () : input file
    outfile () : output file
    processor (FileParser) : IO wrapper
    searcher (SearchTool) : 

    fileopened (bool) : file is currently opened


    Widgets
    -------
    filehistory (wx.FileHistory) : recently opened files widget
    filepanel
    sentpanel
    """
    def __init__(self, parent, *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)

        # constants, no need to reinit on opening next file
        wx.Config.Set(wx.Config("gdisamb", style=wx.CONFIG_USE_LOCAL_FILE))
        self.config = wx.Config.Get(False)
        self.config.SetRecordDefaults()

        x=self.config.ReadInt("MainFrame/pos/x",30)     # JJM : recover previous layout
        y=self.config.ReadInt("MainFrame/pos/y",30)
        w=self.config.ReadInt("MainFrame/size/w",1024)
        h=self.config.ReadInt("MainFrame/size/h",512)
        self.SetPosition(wx.Point(x,y))
        self.SetSize(wx.Rect(x,y,w,h))

        self.statusbar = self.CreateStatusBar(1)
        self.statusbar.SetStatusText('Bienvenue dans la désambiguïsation !')

        def savedDefault(name, fore, back):
            forecolor = self.config.Read("colors/{}/fore".format(name.lower()), fore)
            backcolor = self.config.Read("colors/{}/back".format(name.lower()), back)
            return (name, forecolor, backcolor)
        self.statuscolors = [
            savedDefault("unambiguous", "#1A4780", "#FFFFFF"),
            savedDefault("ambiguous", "#1A4780", "#cccccc"),
            savedDefault("uncertain", "#1A4780", "#dda0dd"),
            savedDefault("unparsed", "#1A4780", "#fc6c85"),
            savedDefault("manual", "#1A4780", "#0bda51"),
            savedDefault("deselected", "Black", "White"),
            savedDefault("selected", "DarkGreen", "White")
        ]

        self.dirname = self.config.Read("state/curdir", os.curdir)
        self.InitValues()

        filemenu = wx.Menu()
        recent = wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN, "O&pen", " Open text file")
        self.Bind(wx.EVT_MENU, self.OnMenuOpen, menuOpen)
        #filemenu.Append(wx.ID_ANY, "Open &recent", recent)
        filemenu.AppendSubMenu(recent,"Open &recent")
        self.filehistory = wx.FileHistory(maxFiles=20, idBase=wx.ID_FILE1)
        self.filehistory.Load(self.config)
        self.filehistory.UseMenu(recent)
        self.filehistory.AddFilesToMenu()
        self.Bind(wx.EVT_MENU_RANGE, self.OnFileHistory, id=wx.ID_FILE1, id2=wx.ID_FILE9)

        # FIXME: move fonts to InitUI?
        self.mainfont = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        savedfont = self.config.Read("fonts/main")
        if savedfont:
            self.mainfont.SetNativeFontInfoUserDesc(savedfont)
            self.SetFont(self.mainfont)

        # FIXME: move menus to InitUI?
        menuSave = filemenu.Append(wx.ID_SAVE, "S&ave", " Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSave, menuSave)
        menuSaveAs = filemenu.Append(wx.ID_SAVEAS, "S&ave as", " Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSaveAs, menuSaveAs)
        menuClose = filemenu.Append(wx.ID_CLOSE, "C&lose", "Close current file")
        self.Bind(wx.EVT_MENU, self.OnClose, menuClose)
        menuSearch = filemenu.Append(wx.ID_FIND, "F&ind", "Find text")
        self.Bind(wx.EVT_MENU, self.OnMenuSearch, menuSearch)
        menuExit = filemenu.Append(wx.ID_EXIT, "E&xit", "Terminate the program")
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu, "&File") # Adding the "filemenu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.
        
        settingsmenu = wx.Menu()
        menuVertical = settingsmenu.Append(wx.ID_ANY, "V&ertical", "Toggle horizontal/vertical display mode")
        self.menuUndoTokens = settingsmenu.Append(wx.ID_ANY, "U&ndo join/split tokens", "Undo join/split tokens")
        self.menuUndoTokens.Enable(False)
        self.Bind(wx.EVT_MENU, self.OnVerticalMode, menuVertical)
        self.Bind(wx.EVT_MENU, self.OnUndoTokens, self.menuUndoTokens)
        menuFont = settingsmenu.Append(wx.ID_ANY, "Select F&ont", "Select font")
        self.Bind(wx.EVT_MENU, self.OnSelectFont, menuFont)
        menuColors = settingsmenu.Append(wx.ID_ANY, "Select &Colors", "Select colors")
        self.Bind(wx.EVT_MENU, self.OnSelectColors, menuColors)
        menuLocaldict = settingsmenu.Append(wx.ID_ANY, "Set &Localdict", "Set Localdict")
        self.Bind(wx.EVT_MENU, self.OnSetLocaldict, menuLocaldict)
            
        self.menuLangBamananGV = wx.MenuItem(settingsmenu, 1, '&Bamanan gloss validation', kind = wx.ITEM_CHECK)   # ADDED JJM
        settingsmenu.Append(self.menuLangBamananGV)
        bamananGV=True # Default
        self.menuLangBamananGV.Check(check = bamananGV)  # IMPROVE : if True, maninkaGV should be False (or not)!!! & vice-versa - see attempt in DoOpen
        self.Bind(wx.EVT_MENU, self.OnSetLangBamananGV, self.menuLangBamananGV)

        self.menuLangManinkaGV = wx.MenuItem(settingsmenu, 2, '&Maninka/N\'ko gloss validation', kind = wx.ITEM_CHECK)   # ADDED JJM 24/03/2024
        settingsmenu.Append(self.menuLangManinkaGV)
        maninkaGV=False # Default
        self.menuLangManinkaGV.Check(check = maninkaGV)  # IMPROVE: should be checked if text.script=N'Ko (see metadict)
        self.Bind(wx.EVT_MENU, self.OnSetLangManinkaGV, self.menuLangManinkaGV)
        
        menuCopy2SpacerToggle= wx.MenuItem(settingsmenu, 3, '&Copy2 Spacer is tab/space toggle', kind = wx.ITEM_CHECK)   # ADDED JJM 04/06/2024
        global copy2spacer
        copy2spacer="\t"
        settingsmenu.Append(menuCopy2SpacerToggle)
        self.Bind(wx.EVT_MENU, self.OnSetCopy2Spacer, menuCopy2SpacerToggle)

        menuBar.Append(settingsmenu, "&Settings")
        self.SetMenuBar(menuBar)
        
        debugmenu = wx.Menu()
        menuInspector = debugmenu.Append(wx.ID_ANY, "Widget I&nspector", "Widget Inspector")
        self.Bind(wx.EVT_MENU, self.OnWidgetInspector, menuInspector)
        menuBar.Append(debugmenu, "&Debug") 

        # Custom events
        self.Bind(EVT_SELECTOR_UPDATED, self.OnSelectorUpdate)
        self.Bind(EVT_SAVE_RESULTS, self.OnSave)
        self.Bind(EVT_TOKEN_SPLIT, self.OnTokenSplit)
        self.Bind(EVT_TOKEN_JOIN, self.OnTokenJoin)
        self.Bind(EVT_TOKEN_EDIT, self.OnTokenEdit)
        self.Bind(EVT_SENTENCE_JOIN, self.OnSentenceJoin)
        self.Bind(EVT_SENTENCE_SPLIT, self.OnSentenceSplit)
        self.Bind(EVT_SENT_EDIT, self.OnSentenceEdit)
        self.Bind(EVT_SATTRS_EDIT, self.OnSentAttrsEdit)
        self.Bind(EVT_LOCALDICT_LOOKUP, self.OnLocaldictLookup)
        self.Bind(EVT_LOCALDICT_SAVE, self.OnLocaldictSave)
        self.Bind(EVT_GLOSS_EDITED, self.OnGlossEdited)

        self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.Sizer)
        self.Show()

    def SetLocaldict(self, dictfile):
        """load localdict from a file or create empty one if the file does not exist"""
        if os.path.exists(dictfile):
            self.oldlocaldict = daba.formats.DictReader(dictfile,keepmrph=True).get()
            # create new local dict - keepmrph important for disamb localdict1
            self.localdict = daba.formats.DabaDict()
            # populate new localdict with notones items
            for x, y in sorted(self.oldlocaldict.items()):
                xnotone=re.sub(r'[\u0301\u0300\u0302\u030c]','',x)  # high, low, decreasing, increasing tone diacritics
                xnotone=xnotone.lower()
                if xnotone in self.localdict:
                    for ygloss in y:
                        if ygloss not in self.localdict[xnotone]:
                            self.localdict[xnotone].insert(0, ygloss)
                else:
                    self.localdict[xnotone]=y[0]
                    for ygloss in y:
                        if ygloss not in self.localdict[xnotone]:
                            self.localdict[xnotone].insert(0, ygloss)
            del self.oldlocaldict
        else:
            self.localdict = daba.formats.DabaDict() # will be populated OnSave

    def InitValues(self):
        """set main attributes"""
        self.infile = None
        self.outfile = None
        self.processor = FileParser()
        self.searcher = SearchTool(self.processor)
        self.logger = None
        self.fileopened = False
        self.undolist = defaultdict(list)

    def InitUI(self):
        """initialize main frame UI"""
        self.notebook = wx.Notebook(self)
        self.filepanel = FilePanel(self.notebook)
        self.sentpanel = SentPanel(self.notebook, vertical=self.config.ReadBool("display/vertical"))
        self.metapanel = MetaPanel(self.notebook)
        self.dictpanel = DictPanel(self.notebook)
        self.notebook.AddPage(self.sentpanel, "Disambiguate")
        self.notebook.AddPage(self.filepanel, "Source")
        self.notebook.AddPage(self.metapanel, "Metas")
        self.notebook.AddPage(self.dictpanel, "Localdict")
        self.Sizer.Add(self.notebook, 1, wx.EXPAND)
        self.Layout()
        self.Bind(wx.EVT_TEXT_ENTER, self.OnButtonSearch, self.sentpanel.searchbutton)
        self.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.OnButtonSearch, self.sentpanel.searchbutton)
        self.Bind(wx.EVT_BUTTON, self.OnFindPrev, self.sentpanel.findprevbutton)
        self.Bind(wx.EVT_BUTTON, self.OnFindNext, self.sentpanel.findnextbutton)
        self.Bind(wx.EVT_SPINCTRL, self.OnGotoSentence, self.sentpanel.sentnumbutton)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnGotoSentence, self.sentpanel.sentnumbutton)
        self.Bind(wx.EVT_BUTTON, self.OnNextAmbig, self.sentpanel.nextambigbutton)

    def CleanUI(self):
        """clear interface"""
        self.SetTitle("no file")
        self.notebook.Destroy()

    def UpdateUI(self):
        """update UI to show SentPanel's current sentence"""
        self.Freeze()
        try:
            snum = self.sentpanel.snum
        except (AttributeError):
            snum = None
        self.CleanUI()
        self.InitUI()
        if snum is not None:
            self.filepanel.ShowFile(s.senttoken for s in self.processor.glosses)
            self.ShowSent(snum)
            self.metapanel.ShowMetas(self.processor.metadata)          
        self.Layout()
        self.Thaw()

    def OnVerticalMode(self, e):
        """toggle vertical mode for UI layout"""
        self.config.WriteBool("display/vertical", not self.config.ReadBool("display/vertical"))
        self.config.Flush()
        if self.fileopened:
            self.UpdateUI()

    def OnSelectFont(self, e):
        """change and save font selected by a user"""
        fontdata = wx.FontData()
        fontdata.SetInitialFont(self.mainfont)
        dlg = wx.FontDialog(self, fontdata)
        if dlg.ShowModal() == wx.ID_OK:
            self.mainfont = dlg.GetFontData().GetChosenFont()
            # FIXME: move to UpdateUI?
            self.SetFont(self.mainfont)
            self.config.Write("fonts/main", self.mainfont.GetNativeFontInfoUserDesc())
            self.config.Flush()
            if self.fileopened:
                self.UpdateUI()
        dlg.Destroy()

    def OnSelectColors(self, e):
        """let user select colors, keep selections in config"""
        dlg = StatusColorsDialog(self, self.config, self.statuscolors)
        if dlg.ShowModal() == wx.ID_OK:
            self.config.Flush()
        dlg.Destroy()

    def OnSetLocaldict(self, e):
        """let user choose localdict for the opened file"""
        if not self.fileopened:
            self.NoFileError(e)
        else:
            dlg = wx.FileDialog(self, "Choose localdict file", self.dirname, "localdict1.txt", "*.*", wx.FD_OPEN)
            if dlg.ShowModal() == wx.ID_OK:
                dictfile = dlg.GetPath()
                self.SetLocaldict(dictfile)
                if not dictfile == '/'.join([self.dirname, "localdict1.txt"]):
                    self.config.Write('/'.join(['localdict', self.infile]), dictfile)
                dlg.Destroy()

    def OnSetLangBamananGV(self, e):  # this does not check / uncheck in Settings ???
        """ let user toggle Bamanan Gloss validation on/off """
        global bamananGV, maninkaGV   # why not just use: self.bamananGV ?
        bamananGV= not bamananGV
        self.menuLangBamananGV.Check(check = bamananGV)
        self.menuLangManinkaGV.Check(check = maninkaGV)
        #print("OnSetLangBamananGV - bamananGV: ",bamananGV,"       maninkaGV: ",maninkaGV)
    
    def OnSetLangManinkaGV(self, e):   # JJM 24/04/2024   # this does not check / uncheck in Settings ???
        """ let user toggle Bamanan Gloss validation on/off """
        global bamananGV, maninkaGV   # why not just use: self.maninkaGV ?
        maninkaGV=not maninkaGV
        self.menuLangBamananGV.Check(check = bamananGV)
        self.menuLangManinkaGV.Check(check = maninkaGV)
        # print("OnSetLangManinkaGV - bamananGV: ",bamananGV,"       maninkaGV: ",maninkaGV)

    def OnSetCopy2Spacer(self,e) : # JJM 04/06/2024
        # use space or tab when spacing ligne 2 elements (lx, ps, gloss) to copy
        global copy2spacer
        if copy2spacer==" ":
            copy2spacer="\t"
        else:
            copy2spacer=" "

    def OnWidgetInspector(self, e):
        """show widget inspector"""
        import wx.lib.inspection
        wx.lib.inspection.InspectionTool().Show()

    def OnSelectorUpdate(self, e):
        """record user's selections/edits into processor"""
        selector = e.GetEventObject()
        if selector.selectlist:
            self.processor.dirty = True
        token = selector.GetWordToken()
        snum, toknum = selector.index
        sent = self.processor.glosses[snum]
        sent.selectlist[toknum] = selector.selectlist
        sent.glosslist[toknum] = token

    def ShowSent(self, snum):
        """show sentence by its index"""
        if self.undolist[snum]:
            self.menuUndoTokens.Enable(True)
        self.SaveFilePos(snum)
        #print("ShowSent snum=",snum, "len(glosses)=",len(self.processor.glosses))
        if snum>=len(self.processor.glosses): snum=0
        self.sentpanel.ShowSent(self.processor.glosses[snum])

    def OnTokenSplit(self, evt):
        """split tokens in the processor glosses data, update UI"""
        snum, toknum = evt.index
        sent = self.processor.glosses[snum]
        savedtoken = sent.glosslist[toknum]
        edit = TokenEdit('split', toknum, toknum+len(evt.result), [savedtoken])
        self.undolist[snum].append(edit)
        del sent.selectlist[toknum]
        del sent.glosslist[toknum]
        shift = 0
        for token in evt.result:
            sent.selectlist.insert(toknum+shift, [])
            sent.glosslist.insert(toknum+shift, daba.formats.WordToken([Gloss(token, (), '', ())], token, '-1'))
            shift = shift+1
        self.processor.dirty = True
        wx.CallAfter(self.ShowSent, snum)

    def OnTokenJoin(self, evt):
        """join tokens in the processor glosses data, update UI"""
        snum = evt.snum
        first = evt.first
        second = evt.second
        sent = self.processor.glosses[snum]
        savedtokens = [2][first:second+1]
        edit = TokenEdit('join', first, second, savedtokens)
        self.undolist[snum].append(edit)
        firsttoken = sent.glosslist[first]
        nexttoken = sent.glosslist[second]
        # FIXME: will break on non-word tokens
        newform = firsttoken.token + nexttoken.token
        newtoken = daba.formats.WordToken([Gloss(newform, (), '', ())], newform, '-1')
        sent.selectlist[first] = []
        del sent.selectlist[second]
        sent.glosslist[first] = newtoken
        del sent.glosslist[second]
        self.processor.dirty = True
        wx.CallAfter(self.ShowSent, snum)

    def OnTokenEdit(self, evt):
        """edit tokens in the processor glosses data, update UI"""
        snum, toknum = evt.index
        sent = self.processor.glosses[snum]
        savedtoken = sent.glosslist[toknum]
        if evt.toktype == 'w':
            if savedtoken.type == 'w':
                newtoken = savedtoken
                newtoken.token = evt.token
            else:
                newtoken = daba.formats.WordToken([Gloss(evt.token, (), '', ())], evt.token, '-1')
        else:
            newtoken = daba.formats.PlainToken((evt.toktype, evt.token))
        sent.glosslist[toknum] = newtoken
        self.processor.dirty = True
        wx.CallAfter(self.ShowSent, snum)

    def OnSentenceJoin(self, evt):
        """join sentences in the processor glosses data, update UI"""
        firstsent = self.processor.glosses[evt.first]
        nextsent = self.processor.glosses[evt.second]
        newsent = firstsent.join(nextsent)
        self.processor.glosses[evt.first] = newsent
        del self.processor.glosses[evt.second]
        for sent in self.processor.glosses[evt.second:]:
            sent.snum -= 1
        self.processor.numsent -= 1
        self.processor.dirty = True
        wx.CallAfter(self.ShowSent, evt.first)

    def OnSentenceSplit(self, evt):
        """split sentences in the processor glosses data, update UI"""
        sent = self.processor.glosses[evt.snum]
        # print("OnSentenceSplit: sent=",sent)
        firstsent, nextsent = sent.split(evt.tnum, evt.charpos)
        self.processor.glosses[evt.snum] = firstsent
        self.processor.glosses.insert(evt.snum+1, nextsent)
        for sent in self.processor.glosses[evt.snum+2:]:
            sent.snum += 1
        self.processor.numsent += 1
        self.processor.dirty = True
        wx.CallAfter(self.ShowSent, evt.snum)

    def OnSentenceEdit(self, evt):
        """save sentence text changes to processor glosses after token edits"""
        sent = self.processor.glosses[evt.snum]
        sent.senttoken = evt.sent
        self.processor.dirty = True

    def OnSentAttrsEdit(self, evt):
        """save sentence-level attributes edits in the processor glosses"""
        sent = self.processor.glosses[evt.snum]
        sent.senttoken.attrs = evt.attrs
        self.processor.dirty = True

    def OnGlossEdited(self, evt):
        """remember that gloss has been edited"""
        self.processor.dirty = True
    
    def OnLocaldictLookup(self, evt):
        """lookup a gloss in localdict, show available matches"""
        global formlookup
        try:

            formlookup=evt.gloss.form


            # JJM : localdict now indexed without tones & lowercase
            formlookup=formlookup.lower()   # all indexed in localdict with no tones and lowercase

            if self.GetTopLevelParent().processor.metadata["text:script"]=="Ancien orthographe malien":
                # form is normally parsed in New Orthography - this only handles exception  (where parse failed, notably Proper names)
                formlookup=formlookup.replace("èe","ɛɛ")
                formlookup=formlookup.replace("òo","ɔɔ")
                formlookup=formlookup.replace("è","ɛ")
                formlookup=formlookup.replace("ò","ɔ") 
            
            formlookup=re.sub(r'[\u0301\u0300\u0302\u030c]','',formlookup)  # 4 bambara tones 
            # print("OnLocaldictLookup - using formlookup: ",formlookup)
            
            savedglosses = self.localdict[formlookup]

            dlg = evt.dlg
            wx.CallAfter(dlg.ShowLocaldictVariants, savedglosses)
        except (KeyError):
            pass

    def OnLocaldictSave(self, evt):
        """save a word into localdict"""
        global formlookup
        # print("OnLocaldictSave - formlookup=",formlookup)
        gloss = evt.gloss
        # we do not save words with empty glosses into localdict
        # original code for this whole section
        """if gloss.form in self.localdict:
            if gloss not in self.localdict[gloss.form]:
                self.localdict[gloss.form].insert(0, gloss)
                print("OnLocalditSave - Added:",gloss, "to entry:",gloss.form)
        else:
            self.localdict[gloss.form] = gloss
            print("OnLocalditSave - Created:",gloss, "to entry:",gloss.form)
        """
        #if not gloss.gloss: JJM changed this, in case there are morphemes
        if not gloss.gloss and not gloss.morphemes:
            return

        if gloss.gloss==None: 
            # rebuild : do not allow None as value for \ge 
            gloss=Gloss(gloss.form, gloss.ps, '', gloss.morphemes)

        # new localdict JJM : is indexed with notones form
        x=gloss.form
        #print("gloss,...", gloss, gloss.form, gloss.ps, gloss.gloss, gloss.morphemes)
        #print("Gloss",Gloss(gloss.form, gloss.ps, gloss.gloss, gloss.morphemes))
        xnotone=re.sub(r'[\u0301\u0300\u0302\u030c]','',x)  # high, low, decreasing, increasing tone diacritics
        xnotone=xnotone.lower()   # allow  proper names to be available even on lower case text 
        #                           there is a side effect with Capitalized entries also created in lowercase on first "Create" ???
        if xnotone in self.localdict and len(gloss.ps)>0 :

            if gloss not in self.localdict[xnotone] :

                self.localdict[xnotone].insert(0, gloss)
                print("OnLocaldictSave - Added to localdict[",xnotone,"] =",gloss)
                
            #else:
            #    print("OnLocaldictSave - Skipped localdict[",xnotone,"] =", gloss, ": already there, do nothing")
        else:
            self.localdict[xnotone] = gloss
            print("OnLocaldictSave - Created localdict[",xnotone,"] =",gloss)

        if xnotone!=formlookup and len(gloss.ps)>0 :
            # this will add an entry if token!=form so that future erroneous token may yield correct form lookup.
            print(xnotone,"<>",formlookup," : essayer de l'indexer?")
            if formlookup not in self.localdict:
                self.localdict[formlookup] = gloss
                print("¹OnLocaldictSave - also created localdict[",formlookup,"] =",gloss)
            elif gloss not in self.localdict[formlookup]:
                self.localdict[formlookup] = gloss
                print("ajout de localdict["+formlookup+"] =",gloss)
                print("récap de localdict["+formlookup+"] =")
                for g in self.localdict[formlookup]:
                    print("-",str(g))
#            if formlookup not in self.localdict:
#                self.localdict[formlookup] = gloss
#                print("¹OnLocaldictSave - also created localdict[",formlookup,"] =",gloss)
#            elif xnotone not in self.localdict:
#                self.localdict[xnotone] = gloss
#                print("²OnLocaldictSave - also created localdict[",xnotone,"] =",gloss)
#            else:
#                print(formlookup,"ou",xnotone,"déjà dans localdict")
#                try: 
#                    self.localdict[xnotone] = gloss
#                    print('on indexe quand même')
#                except:
#                    print('ajout impossible')

    def OnUndoTokens(self, e):
        """undo token split/join operations"""
        snum = self.sentpanel.snum
        if self.undolist[snum]:
            savedstate = self.undolist[snum].pop()
            sent = self.processor.glosses[snum]
            if savedstate.operation == 'split':
                sent.glosslist[savedstate.start:savedstate.end+1] = savedstate.toklist
            elif savedstate.operation == 'join':
                sent.glosslist[savedstate.start:savedstate.end] = savedstate.toklist
            else:
                print("Unimplemented undo operation!")
            self.ShowSent(snum)

    def OnMenuSearch(self, e):
        """pop-up search dialog"""
        dlg = SearchDialog(self, wx.ID_ANY, "Search word or sentence part", "")
        if (dlg.ShowModal() == wx.ID_OK):
            searchstr = dlg.GetSearchString()
            self.DoSearch(searchstr)

    def OnButtonSearch(self, e):
        """run search when search button is pressed"""
        searchstr = self.sentpanel.searchbutton.GetValue()
        self.DoSearch(searchstr)

    def DoSearch(self, searchstr):
        """run search for a given query"""
        if not searchstr:
            return
        # search forward by default
        firstmatch = self.searcher.find(searchstr, startsent=self.sentpanel.snum)
        self.ShowSearchResult(firstmatch)

    def ShowSearchResult(self, match):
        """show the first sentence where the string is found"""
        if not self.searcher.searchstr:
            return
        if not match:
            notf = NotFoundDialog(self, wx.ID_ANY, "Not found", self.searcher.searchstr)
            notf.ShowModal()
        else:
            snum, pos = match
            # FIXME: wnum is ignored until we could recenter panel on the given word
            if snum != self.sentpanel.snum:
                self.ShowSent(snum)
            else:
                if len(self.searcher.matches) == 1:
                    foundhere = wx.MessageDialog(self, "Found in this sentence only!", "Search result", wx.OK)
                    foundhere.ShowModal()

    def OnFindPrev(self, e):
        """show previous match"""
        match = self.searcher.findPrev()
        self.ShowSearchResult(match)

    def OnFindNext(self, e):
        """show next match"""
        match = self.searcher.findNext()
        self.ShowSearchResult(match)

    def OnNextAmbig(self, e):
        snum = self.sentpanel.sentnumbutton.GetValue() # start at current sentence
        #print("OnNextAmbig - starting at sentence # ",snum)
        ns=0
        ambig=False
        for s in self.processor.glosses:
            ns+=1
            if ns>snum:  # only check sentences after the current one
                #print(" OnNextAmbig - checking sentence # ",ns)
                for g in s.glosslist:
                    if g.type=="w":
                        if len(g.value[2])!=1:   # >1 : ambigu   0 : inconnu
                            #print("   ",g)
                            #print("   ",g.value[2])
                            ambig=True
                            break
                        else: # only one gloss but problems
                            if len(g.gloss.ps)==0 and g.gloss.gloss=='':  # word in red (no gparser candidate)
                                #print("   ",g)
                                ambig=True
                                break
                            elif g.gloss.gloss=='INCOGN':
                                #print("   ",g)
                                ambig=True
                                break
            if ambig: break
        if ambig: self.ShowSent(ns-1)
        

    def OnGotoSentence(self, e):
        """show sentence with a given number"""
        self.sentpanel.OnSaveResults(e)
        snum = self.sentpanel.sentnumbutton.GetValue() - 1
        self.ShowSent(snum)

    def SaveFilePos(self, snum):
        """save current sentence index for a file"""
        if self.fileopened:
            self.config.WriteInt(self.infile, snum)
            self.config.Flush()

    def GetFilePos(self, filename):
        """recall the saved sentence index for a file"""
        snum = self.config.ReadInt(filename, 0)
        return snum

    def OnClose(self, e):
        """save and cleanup UI on file close"""

        if self.fileopened:
            #   JJM save window position and size
            x,y=self.Position 
            w,h=self.Size
            #print ("x,y - w,h :",x,y,w,h)
            
            self.config.WriteInt("MainFrame/pos/x",x)
            self.config.WriteInt("MainFrame/pos/y",y)
            self.config.WriteInt("MainFrame/size/w",w)
            self.config.WriteInt("MainFrame/size/h",h)
            self.config.Flush()  # permanently writes
            
            if self.processor.dirty:
                self.OnSave(e)
            if self.logger:
                self.logger.OnExit()
            self.InitValues()
            self.CleanUI()

    def OnExit(self, e):
        """close file on exit"""
        if self.fileopened:
            self.OnClose(e)
        self.Close(True)

    def NoFileError(self, e):
        """show error message that no file is opened"""
        dlg = wx.MessageDialog(self, 'Error: no file opened!', 'No file opened', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()
 
    def FileOpenedError(self, e):
        """show error message that file is not closed"""
        dlg = wx.MessageDialog(self, 'Error: previous file not closed!', 'Previous file is still opened. You should close it before opening the next one', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnMenuOpen(self, e):
        """pop-up open file menu"""
        if self.fileopened:
            self.FileOpenedError(e)
        else:
            #dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.FD_OPEN)
            dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "disamb files|*.pars.html;*.repl.html;*.dis.html", wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
            if dlg.ShowModal() == wx.ID_OK:
                self.DoOpen(dlg.GetPath())
                dlg.Destroy()

    def OnFileHistory(self, e):
        """open a file from recent files"""
        if self.fileopened:
            self.FileOpenedError(e)
        else:
            filenum = e.GetId() - wx.ID_FILE1
            self.DoOpen(self.filehistory.GetHistoryFile(filenum))

    def DoOpen(self, filename):
        """ Open a file"""
        self.infile = filename
        self.filehistory.AddFileToHistory(self.infile)
        self.filehistory.Save(self.config)
        self.dirname = os.path.dirname(self.infile)
        self.config.Write("state/curdir", self.dirname)
        self.config.Flush()
        self.filename = os.path.basename(self.infile)
        logfile = os.path.extsep.join([get_basename(self.infile), 'log'])
        self.logger = EditLogger(os.path.join(self.dirname, logfile))
        self.dictfile = self.config.Read("/".join(["localdict", self.infile]), os.path.join(self.dirname, "localdict1.txt"))
        self.SetLocaldict(self.dictfile)
        self.processor.read_file(self.infile)
        self.nambigs_before,self.totalwords_before=self.nambigs()
        pcdisamb=0
        if self.totalwords_before>0 : pcdisamb=int(100*self.nambigs_before/self.totalwords_before)
        self.statusbar.SetStatusText(str(self.nambigs_before)+' mots ambigus restants/'+str(self.totalwords_before)+" mots au total soit "+str(pcdisamb)+"%")

        self.InitUI()
        self.SetTitle(self.filename)
        self.filepanel.ShowFile(s.senttoken for s in self.processor.glosses)
        self.metapanel.ShowMetas(self.processor.metadata)
        self.dictpanel.ShowDict(self.dictfile)
        
        snum = self.GetFilePos(self.infile)
        self.ShowSent(snum)
        self.fileopened = True
        self.Layout()

        #this does not do anything useful
        global bamananGV,maninkaGV
        metadict=self.processor.metadata
        if "text:script" in metadict:
            textscript=metadict["text:script"]
            if textscript in ["Ancien orthographe malien","Nouvel orthographe malien"]:
                bamananGV=True
                maninkaGV=False
            elif textscript in["N’Ko","Nouveau orthographe guinéen", "Ancien orthographe guinéen"]:
                bamananGV=False
                maninkaGV=True
            self.menuLangBamananGV.Check(check = bamananGV)
            self.menuLangManinkaGV.Check(check = maninkaGV) 

    def nambigs(self):   # JJM compute ambiguous words left
        na=0
        nw=0
        for s in self.processor.glosses:
            for g in s.glosslist:
                if g.type=="w":
                    nw += 1
                    if len(g.value[2])>1: na += 1
        return na,nw

    def SaveFiles(self):
        """save annotated data, localdict and config values"""
        
        prevsent=self.processor.metadata["_auto:sentences"]   # JJM
        prevwords=self.processor.metadata["_auto:words"]
        # JJM : if there are splits/joins these meta will be updated next in processor.write (FileParser)
        self.processor.write(self.outfile)
        self.config.Flush()
        
        # save localdict AFTER annotated data: i case of problem with localdict, disamb is saved with higher priority
        if self.localdict:
            """print("SaveFiles, before DictWriter")
            for x, y in sorted(self.localdict.items()):
                print("localdict[",x,"]=",y)
            """
            daba.formats.DictWriter(self.localdict, self.dictfile, lang='default', name='localdict', ver='0').write()
            self.dictpanel.ShowDict(self.dictfile)      #  needs to be updated only if localdict is updated
        
        
        nambigs_after,totalwords_after=self.nambigs()
        
        if self.processor.metadata["_auto:sentences"]!=prevsent or self.processor.metadata["_auto:words"]!=prevwords:

            self.filepanel.ShowFile(s.senttoken for s in self.processor.glosses)   # also needs update when sentence fully disambed
            self.metapanel.ShowMetas(self.processor.metadata)           # may also need to be updated on words split/joins            
            
        if nambigs_after != self.nambigs_before or totalwords_after != self.totalwords_before :
            self.filepanel.ShowFile(s.senttoken for s in self.processor.glosses)   # update as sentence is disambed
            self.nambigs_before=nambigs_after
            self.totalwords_before=totalwords_after
            pcdisamb=int(100*nambigs_after/totalwords_after)
            self.statusbar.SetStatusText(str(self.nambigs_before)+' mots ambigus restants/'+str(totalwords_after)+" mots au total soit "+str(pcdisamb)+"%")

    def OnSave(self, e):
        """save files"""
        if not self.fileopened:
            self.NoFileError(e)
        else:
            if not self.outfile:
                self.OnSaveAs(e)
            else:
                self.SaveFiles()

    def OnSaveAs(self, e):
        """pop-up save as menu"""
        if not self.fileopened:
            self.NoFileError(e)
        else:
            xfilename = ''.join(['.'.join([get_basename(self.infile), 'dis']), os.path.extsep, 'html'])

            dlg = wx.FileDialog(self, "Choose a file", os.path.dirname(self.infile), xfilename, "*.html", wx.FD_SAVE)
            if dlg.ShowModal() == wx.ID_OK:
                self.outfile = dlg.GetPath()
                if not os.path.splitext(self.outfile)[1] == '.html' :
                    self.outfile = ''.join([self.outfile, os.path.extsep, 'html'])
                self.SaveFiles()
                self.filehistory.AddFileToHistory(self.outfile)
                # added JJM
                self.filehistory.Save(self.config)
                self.dirname = os.path.dirname(self.outfile)
                self.config.Write("state/curdir", self.dirname)
                self.config.Flush()
                self.filename = os.path.basename(self.outfile)
                self.SetTitle(self.filename)
                # end added JJM
            dlg.Destroy()


def main():
    app = wx.App()

    frame = MainFrame(None, title="Daba disambiguation interface (GUI)")
    frame.Show()

    app.MainLoop()
    

if __name__ == '__main__':
    main()

