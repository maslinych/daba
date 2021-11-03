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
    if pars > 0:
        return basename[:pars]
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
    senntoken (PlainToken) : sentence token
    senttext (str) : sentence text
    glosslist ([WordToken]) : list of anntotations for each token in a sentence
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
        """split sentence into two SentAnnot objs at the given point"""
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
        if self.ignorecase:
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

        event.Skip()


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
    def __init__(self, parent, gloss, statecolours, disabled=False,
                 *args, **kwargs):
        """GlossButton constructor

        :param gloss: Gloss to be displayed on the button
        :type gloss: Gloss
        :param statecolors: colors for vairous state of the selector
        :type statecolors: dict"""
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.selected = False
        self.children = []
        self.gloss = gloss
        self.disabled = disabled
        self.statecolours = statecolours

        box = wx.BoxSizer(wx.VERTICAL)
        # prepare main gloss button
        if self.disabled:
            self.main = wx.Button(self, -1, makeGlossString(gloss))
            self.main.Disable()
        else:
            self.main = wx.ToggleButton(self, -1, makeGlossString(gloss))
            self.main.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggled)
        fore, back = self.statecolours['deselected']
        self.main.SetForegroundColour(fore)
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
            self.main.SetBackgroundColour(back)
        else:
            fore, back = self.statecolours['deselected']
            self.main.SetForegroundColour(fore)
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
        vbox_top.Add(wx.StaticText(self, wx.ID_ANY,
                                   "Gloss string (edit inplace):"))
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

    def UpdateInterface(self, gloss):
        """update dialog (gbutton, glosstext) given a gloss"""
        self.freeze = True
        glossstring = str(gloss)
        cursor = self.glosstext.GetInsertionPoint()
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
        if not self.freeze:
            self.FitGlosstextWidth()
            glosstext = normalizeText(self.glosstext.GetValue())
            oldgloss = self.as_gloss
            try:
                toks = daba.grammar.str_tokenize(glosstext)
                self.as_gloss = daba.grammar.stringgloss_parser().parse(toks)
                if not self.as_gloss == oldgloss:
                    self.glosstext.SetBackgroundColour(wx.NullColour)
                    self.glosstext.Refresh()
                    self.UpdateInterface(self.as_gloss)
                else:
                    self.glosstext.SetBackgroundColour('yellow')
                    self.glosstext.Refresh()
            except (LexerError, NoParseError):
                self.glosstext.SetBackgroundColour('yellow')
                self.glosstext.Refresh()

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
        dlg = GlossInputDialog(self, wx.ID_ANY, 'Insert gloss manually', gloss=self.gloss)
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
        if len(self.glosslist) > 1:
            for gloss in glosslist:
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
            self.joinfwID = wx.NewId()
            self.joinbwID = wx.NewId()
            self.splitID = wx.NewId()
            self.changeID = wx.NewId()

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
        for btn in tokenbuttons:
            token = btn.token.token
            charlength = len(token)
            tokenindex = self.text[startchar:].find(token)
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
        sentevent = SentenceEditEvent(self.GetId(), snum=snum, sent=self.token)
        wx.PostEvent(self.GetEventHandler(), sentevent)

    def Highlight(self, start, end):
        """highlight characters between start and end (not implemented)"""
        pass

    def OnContextMenu(self, evt):
        """pop-up sentence context menu on right-click"""
        if not hasattr(self, "joinfwID"):
            self.splitID = wx.NewId()
            self.joinfwID = wx.NewId()
            self.joinbwID = wx.NewId()

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
        if charpos < last:
            first = self.intervals.overlap(0, charpos)
            # make sure that second part contains tokens
            if len(first) < len(self.charspans):
                snum = self.sentpanel.snum
                tnum = len(first)
                ssplitevent = SentenceSplitEvent(self.GetId(), snum=snum, tnum=tnum, charpos=charpos)
                wx.PostEvent(self.GetEventHandler(), ssplitevent)
            


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
            alist.sort()
            for keytext, value in alist:
                key = wx.StaticText(self, wx.ID_ANY, keytext)
                field = wx.TextCtrl(self, wx.ID_ANY, value)
                field.Bind(wx.EVT_TEXT, self.OnEditValue)
                delbutton = wx.Button(self, wx.ID_ANY, style=wx.BU_EXACTFIT | wx.BU_NOTEXT)
                delbutton.SetBitmapLabel(wx.ArtProvider.GetBitmap(wx.ART_DELETE | wx.ART_MENU))
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

    def ShowFile(self, sentlist):
        """show source text for a file"""
        Sizer = wx.BoxSizer(wx.VERTICAL)
        for n, senttoken in enumerate(sentlist):
            st = SentText(self, -1, num=n, style=wx.ST_NO_AUTORESIZE)
            st.SetLabel(senttoken.value)
            st.Wrap(self.GetClientSize().GetWidth()-20)
            st.Bind(wx.EVT_LEFT_DOWN, st.onMouseEvent)
            Sizer.Add(st, 1, wx.EXPAND)

        self.SetSizer(Sizer)
        self.Layout()


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
        self.findprevbutton = wx.Button(self, wx.ID_ANY, '<Prev')
        self.findnextbutton = wx.Button(self, wx.ID_ANY, 'Next>')
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
        self.navsizer.Add(savebutton, 0)
        self.navsizer.Add(self.searchbutton, 0, wx.EXPAND)
        self.navsizer.Add(self.findprevbutton, 0)
        self.navsizer.Add(self.findnextbutton, 0)
        copybutton = wx.Button(self, wx.ID_COPY)
        copybutton.Bind(wx.EVT_BUTTON, self.OnCopyToClipboard)
        self.navsizer.Add(copybutton)
        self.sentsource = SentenceText(self)
        self.sentattrs = SentAttributes(self)
        self.Sizer.Add(self.navsizer)
        self.Sizer.Add(self.sentsource, 0, wx.EXPAND)
        self.Sizer.Add(self.sentattrs, 0, wx.EXPAND)
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
        filemenu.Append(wx.ID_ANY, "Open &recent", recent)
        self.filehistory = wx.FileHistory(maxFiles=9, idBase=wx.ID_FILE1)
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
            self.localdict = daba.formats.DictReader(dictfile).get()
        else:
            self.localdict = daba.formats.DabaDict()

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
        self.notebook.AddPage(self.sentpanel, "Disambiguate")
        self.notebook.AddPage(self.filepanel, "Source")
        self.Sizer.Add(self.notebook, 1, wx.EXPAND)
        self.Layout()
        self.Bind(wx.EVT_TEXT_ENTER, self.OnButtonSearch, self.sentpanel.searchbutton)
        self.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.OnButtonSearch, self.sentpanel.searchbutton)
        self.Bind(wx.EVT_BUTTON, self.OnFindPrev, self.sentpanel.findprevbutton)
        self.Bind(wx.EVT_BUTTON, self.OnFindNext, self.sentpanel.findnextbutton)
        self.Bind(wx.EVT_SPINCTRL, self.OnGotoSentence, self.sentpanel.sentnumbutton)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnGotoSentence, self.sentpanel.sentnumbutton)

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
            dlg = wx.FileDialog(self, "Choose localdict file", self.dirname, "localdict.txt", "*.*", wx.FD_OPEN)
            if dlg.ShowModal() == wx.ID_OK:
                dictfile = dlg.GetPath()
                self.SetLocaldict(dictfile)
                if not dictfile == '/'.join([self.dirname, "localdict.txt"]):
                    self.config.Write('/'.join(['localdict', self.infile]), dictfile)
                dlg.Destroy()

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
        try:
            savedglosses = self.localdict[evt.gloss.form]
            dlg = evt.dlg
            wx.CallAfter(dlg.ShowLocaldictVariants, savedglosses)
        except (KeyError):
            pass

    def OnLocaldictSave(self, evt):
        """save a word into localdict"""
        gloss = evt.gloss
        # we do not save words with empty glosses into localdict
        if not gloss.gloss:
            return
        if gloss.form in self.localdict:
            if gloss not in self.localdict[gloss.form]:
                self.localdict[gloss.form].insert(0, gloss)
        else:
            self.localdict[gloss.form] = gloss
    
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
            dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.FD_OPEN)
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
        self.dictfile = self.config.Read("/".join(["localdict", self.infile]), os.path.join(self.dirname, "localdict.txt"))
        self.SetLocaldict(self.dictfile)
        self.processor.read_file(self.infile)
        self.InitUI()
        self.SetTitle(self.filename)
        self.filepanel.ShowFile(s.senttoken for s in self.processor.glosses)
        snum = self.GetFilePos(self.infile)
        self.ShowSent(snum)
        self.fileopened = True
        self.Layout()

    def SaveFiles(self):
        """save annotated data, localdict and config values"""
        if self.localdict:
            daba.formats.DictWriter(self.localdict, self.dictfile, lang='default', name='localdict', ver='0').write()
        self.processor.write(self.outfile)
        self.config.Flush()

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
            dlg.Destroy()


def main():
    app = wx.App()
    frame = MainFrame(None, title="Daba disambiguation interface (GUI)")
    frame.Show()
    app.MainLoop()
    

if __name__ == '__main__':
    main()

