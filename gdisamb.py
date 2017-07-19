#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Manual disambiguation editor
#
# Copyright (C) 2010—2013  Kirill Maslinsky <kirill@altlinux.org>
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

import formats
import grammar
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError
from intervaltree import IntervalTree
from ntgloss import Gloss


## EVENTS 

GlossSelectorEvent, EVT_SELECTOR_UPDATED = wx.lib.newevent.NewCommandEvent()
GlossButtonEvent, EVT_GLOSS_SELECTED = wx.lib.newevent.NewCommandEvent()
GlossEditEvent, EVT_GLOSS_EDITED = wx.lib.newevent.NewCommandEvent()
TokenSplitEvent, EVT_TOKEN_SPLIT = wx.lib.newevent.NewCommandEvent()
TokenJoinEvent, EVT_TOKEN_JOIN = wx.lib.newevent.NewCommandEvent()
TokenEditEvent, EVT_TOKEN_EDIT = wx.lib.newevent.NewCommandEvent()
SentenceEditEvent, EVT_SENT_EDIT = wx.lib.newevent.NewCommandEvent()
ShowSelectorEvent, EVT_SHOW_SELECTOR = wx.lib.newevent.NewCommandEvent()
SaveResultsEvent, EVT_SAVE_RESULTS = wx.lib.newevent.NewCommandEvent()
LocaldictLookupEvent, EVT_LOCALDICT_LOOKUP = wx.lib.newevent.NewCommandEvent()
LocaldictSaveEvent, EVT_LOCALDICT_SAVE = wx.lib.newevent.NewCommandEvent()


## UTILITY functions and no-interface classes

def normalizeText(t):
    return unicodedata.normalize('NFKD', unicode(t))

TokenEdit = namedtuple('TokenEdit', 'operation start end toklist')


def get_basename(fname):
    basename = os.path.splitext(os.path.basename(fname))[0]
    pars = basename.rfind('.pars')
    if pars > 0:
        return basename[:pars]
    dis = basename.rfind('.dis')
    if dis > 0 and len(basename)-dis <= 7:
        return basename[:dis]
    return basename


class NormalizedTextCtrl(wx.TextCtrl):
    def __init__(*args, **kwargs):
        if len(args) > 3:
            arglist = list(args)
            arglist[3] = normalizeText(args[3])
        if 'value' in kwargs:
            kwargs['value'] = normalizeText(kwargs['value'])

        wx.TextCtrl.__init__(*args, **kwargs)

    def SetValue(self, string):
        wx.TextCtrl.SetValue(self, normalizeText(string))


def makeGlossString(gloss, morphemes=False):
    if not ''.join(gloss.ps) and not gloss.gloss and not gloss.morphemes:
        return gloss.form
    elif morphemes and gloss.morphemes:
        return u'{0} ({1}){3}{2}{4}'.format(gloss.form, '/'.join(gloss.ps), gloss.gloss, os.linesep, '\n' + os.linesep.join([unicode(m) for m in gloss.morphemes]))
    else:
        return u'{0} ({1}){3}{2}'.format(gloss.form, '/'.join(gloss.ps), gloss.gloss, os.linesep)


class FileParser(object):
    def __init__(self):
        self.glosses = []
        self.dirty = False

    def read_file(self, filename):
        freader = formats.HtmlReader(filename)
        self.metadata = freader.metadata
        self.glosses = []
        for pnum, par in enumerate(freader.glosses):
            for snum, sent in enumerate(par):
                # tuple(sent_text, selectlist, glosslist, index)
                self.glosses.append((sent[0], [[] for i in sent[1]], sent[1], (pnum, snum)))
                self.numsent = freader.numsent
                self.numwords = freader.numwords

    def write(self, filename):
        out = [[]]
        for sent in self.glosses:
            pnum = sent[3][0]
            if pnum > len(out)-1:
                out.append([])
            outgloss = []
            for selectlist, glosstoken in zip(sent[1], sent[2]):
                if not selectlist:
                    outgloss.append(glosstoken)
                else:
                    if glosstoken.type == 'w':
                        glosstoken.setGlosslist(selectlist)
                    outgloss.append(glosstoken)
            out[-1].append((sent[0], outgloss))
        fwriter = formats.HtmlWriter((self.metadata, out), filename)
        fwriter.write()


class EditLogger(object):
    def __init__(self, filename, encoding='utf-8'):
        self.fileobj = codecs.open(filename, 'a+', encoding=encoding)

    @property
    def timestamp(self):
        return datetime.datetime.now().isoformat()

    def LogEdit(self, firstgloss, secondgloss):
        self.fileobj.write(u'{0}\n'.format('\t'.join([self.timestamp, 'edit', unicode(firstgloss), unicode(secondgloss)])))

    def LogSplit(self, srctoken, tokentuple):
        self.fileobj.write(u'{0}\n'.format('\t'.join([self.timestamp, 'split', srctoken, ''.join(tokentuple)])))

    def LogJoin(self, srctuple, restoken):
        self.fileobj.write(u'{0}\n'.format('\t'.join([self.timestamp, 'join', ''.join(srctuple), restoken])))

    def OnExit(self):
        self.fileobj.close()


class SearchTool(object):
    def __init__(self, processor):
        self.processor = processor
        self.history = []
        self.matches = []
        self.position = 0
        self.ignorecase = True
        self.searchstr = ""

    @property
    def nmatches(self):
        return len(self.matches)

    def _searcher(self, searchstr, searchtype, startsent):
        self.position = 0
        self.matches = []
        self.searchstr = searchstr
        self.history.append(self.searchstr)
        if self.ignorecase:
            searchstr = searchstr.lower()
            glosses = list(enumerate(self.processor.glosses))
        if startsent:
            glosses = glosses[startsent:] + glosses[:startsent]
        for snum, sent in glosses:
            if searchtype == 'word part':
                for wnum, word in enumerate(sent[2]):
                    try:
                        if self.searchstr in word.token:
                            match = (snum, wnum)
                            self.matches.append(match)
                    # FIXME: should not happen if all words are proper GlossTokens
                    except (AttributeError):
                        print word
            elif searchtype == 'sentence part':
                for matchobj in re.finditer(self.searchstr, sent[0]):
                    self.matches.append((snum, matchobj))
        return self.matches
        
    def find(self, searchstr, startsent=0):
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
        if self.matches:
            self.position += 1
            if self.position >= len(self.matches):
                self.position -= len(self.matches)
            return self.matches[self.position]
        else:
            return ()

    def findPrev(self):
        if self.matches:
            self.position -= 1
            if self.position < 0:
                self.position = len(self.matches) + self.position
            return self.matches[self.position]
        else:
            return ()


## WIDGETS

class SentText(wx.StaticText):
    def __init__(self, parent, id, num=None, *args, **kwargs):
        wx.StaticText.__init__(self, parent, *args, **kwargs)
        self.num = num
        self.parent = parent

    def onMouseEvent(self, event):
        if event.Moving():
            self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        elif event.LeftDown():
            self.GetTopLevelParent().sentpanel.OnSaveResults(event)
            self.GetTopLevelParent().ShowSent(self.num)
            self.GetTopLevelParent().Layout()

        event.Skip()


class GlossButton(wx.Panel):
    def __init__(self, parent, gloss, statecolours, disabled=False, *args, **kwargs):
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
                m = GlossButton(self, morph, self.statecolours, disabled=self.disabled)
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
        for child in self.children:
            if bool(child.main.GetValue()) != self.selected:
                child.main.SetValue(self.selected)
                child.DoToggle()


class GlossInputDialog(wx.Dialog):
    def __init__(self, parent, id, title, gloss, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title,
                           style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER,
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
        vbox_top.Add(wx.StaticText(self, wx.ID_ANY, "Gloss string (edit inplace):"))
        glossstring = unicode(self.as_gloss)
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
        gwidth, gheight = self.glosstext.GetTextExtent(self.glosstext.GetValue())
        self.GetSizer().SetItemMinSize(self.glosstext, (gwidth + 15, gheight + 10))
        self.Layout()
        self.Fit()

    def UpdateInterface(self, gloss):
        self.freeze = True
        glossstring = unicode(gloss)
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
        for gloss in savedglosses:
            if not gloss == self.as_gloss:
                self.glosstext.Append(unicode(gloss))
    
    def SetGlossAttr(self, **kwargs):
        self.as_gloss._replace(**kwargs) 

    def GetGloss(self):
        return self.as_gloss

    def OnEditGlosstext(self, evt):
        if not self.freeze:
            self.FitGlosstextWidth()
            glosstext = normalizeText(self.glosstext.GetValue())
            oldgloss = self.as_gloss
            try:
                toks = grammar.str_tokenize(glosstext)
                self.as_gloss = grammar.stringgloss_parser().parse(toks)
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
        self.save = not self.save


class TokenSplitDialog(wx.Dialog):
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
        pos = self.formfield.GetInsertionPoint()
        last = self.formfield.GetLastPosition()
        if not pos == 0 and not pos == last:
            first = self.formfield.GetRange(0,pos)
            second = self.formfield.GetRange(pos,last)
            self.split = (first, second)
            sizer = self.GetSizer()
            sizer.Detach(self.splittext)
            self.splittext.Show(False)
            self.splittext = wx.StaticText(self, wx.ID_ANY, ' | '.join(self.split))
            sizer.Insert(2, self.splittext, 0, wx.EXPAND)
            self.Layout()

    def GetResult(self):
        return self.split


class GlossEditButton(wx.Panel):
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
        """Setup a gloss to show as current selection"""
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
            print 'Unknown state code:', statecode


class GlossSelector(wx.Panel):
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
        if len(self.glosslist) > 1:
            for gloss in glosslist:
                gbutton = GlossButton(self, gloss, self.statecolours)
                self.children.append(gbutton)
                self.sizer.Add(gbutton, 0, *self.sizerflags)
            self.SetSizer(self.sizer)
            self.Layout()

    def UpdateState(self, statecode, gloss):
        self.mbutton.OnStateChange(self.statecode, self.gloss)

    def OnEdition(self, evt):
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
        evt = GlossSelectorEvent(self.GetId())
        evt.SetEventObject(self)
        wx.PostEvent(self.GetEventHandler(), evt)
        self.Layout()

    def OnSelection(self, gloss):
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
                print "Bug: Negative selection!", selected
        else:
            self.gloss = gloss
            self.glosslist = [gloss]
            self.selectlist = [gloss]
            self.statecode = 5
            self.stage = 'gdisamb.-1'
        self.UpdateState(self.statecode, self.gloss)

    def GetToken(self):
        return formats.GlossToken((self.toktype, (self.form, self.stage, self.glosslist)))

    def OnContextMenu(self, evt):
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
        #FIXME: not implemented yet
        change.Enable(False)

        #FIXME: lacks elegance, duplicate code, see JoinTwo
        glosses = self.GetTopLevelParent().processor.glosses
        sentpanel = self.GetTopLevelParent().sentpanel
        tokens = glosses[sentpanel.snum][2]
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
        snum, toknum = self.index
        self.OnJoinTwo(snum, toknum, toknum+1)

    def OnJoinBackward(self, evt):
        snum, toknum = self.index
        self.OnJoinTwo(snum, toknum-1, toknum)

    def OnJoinTwo(self, snum, first, second):
        joinevent = TokenJoinEvent(self.GetId(), snum=snum, first=first, second=second)
        wx.PostEvent(self.GetEventHandler(), joinevent)

    def OnSplitToken(self, evt):
        dlg = TokenSplitDialog(self,self.form)
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.GetResult()
            if len(result) > 1:
                splitevent = TokenSplitEvent(self.GetId(), index=self.index, result=result)
                wx.PostEvent(self.GetEventHandler(), splitevent)

    def OnChangeTokenType(self, evt):
        pass


class TokenInputDialog(wx.Dialog):
    def __init__(self, parent, id, title, tokentype, tokenstr, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)
        self.typedict = dict([("Comment", "Comment"), ("Punctuation", "c"), ("Markup", "Tag"), ("Word", "w")])

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.tokenfield = NormalizedTextCtrl(self, wx.ID_ANY, tokenstr)
        sizer.Add(self.tokenfield)
        self.typefield = wx.RadioBox(self, wx.ID_ANY, "Token type", wx.DefaultPosition, wx.DefaultSize, self.typedict.keys(), 1)
        self.typefield.SetStringSelection(dict((v,k) for k,v in self.typedict.items())[tokentype])
        sizer.Add(self.typefield)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)

    def GetToken(self):
        return (self.typedict[self.typefield.GetStringSelection()], self.tokenfield.GetValue())

class SearchDialog(wx.Dialog):
    def __init__(self, parent, id, title, searchstr, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.searchfield = NormalizedTextCtrl(self, wx.ID_ANY, searchstr)
        sizer.Add(wx.StaticText(self, wx.ID_ANY, "Search for word or sentence part:"))
        sizer.Add(self.searchfield)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)

    def GetSearchString(self):
        return self.searchfield.GetValue()


class NotFoundDialog(wx.Dialog):
    def __init__(self, parent, id, title, searchstr, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, -1, u'String "{0}" not found'.format(searchstr)))
        sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)


class StatusColorsDialog(wx.Dialog):
    def __init__(self, parent, config, statuscolors, *args, **kwargs):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, "Select status colors", *args, **kwargs)
        self.config = config
        self.buttonrefs = {}
        sizer = wx.BoxSizer(wx.VERTICAL)
        buttonSizer = wx.FlexGridSizer(7, 5)
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
        name, side, sampletext = self.buttonrefs[evt.GetId()]
        colorstring = wx.Colour(*evt.GetValue()).GetAsString(wx.C2S_HTML_SYNTAX)
        self.config.Write("colors/{0}/{1}".format(name, side), colorstring)
        if side == 'fore':
            sampletext.SetForegroundColour(colorstring)
        elif side == 'back':
            sampletext.SetBackgroundColour(colorstring)

        
class TokenEditButton(wx.Panel):
    def __init__(self, parent, index, tokentype, tokenstr, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.index = index
        self.tokenstr = tokenstr
        self.tokentype = tokentype
        self.button = wx.Button(self, wx.ID_ANY, self.tokenstr, style=wx.NO_BORDER)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.button,0)
        self.SetSizer(sizer)
        self.button.Bind(wx.EVT_BUTTON, self.OnEditToken)

    def OnEditToken(self, event):
        dlg = TokenInputDialog(self, wx.ID_ANY, 'Edit token', self.tokentype, self.tokenstr)
        if (dlg.ShowModal() == wx.ID_OK):
            self.tokentype, self.tokenstr = dlg.GetToken()
            self.button.SetLabel(self.tokenstr)
            editevent = TokenEditEvent(self.GetId(), index = self.index, toktype=self.tokentype, token=self.tokenstr)
            wx.PostEvent(self.GetEventHandler(), editevent)
        dlg.Destroy()

    def GetToken(self):
        return (self.tokentype, self.tokenstr)


class SentenceText(wx.stc.StyledTextCtrl):
    def __init__(self, parent, *args, **kwargs):
        wx.stc.StyledTextCtrl.__init__(self, parent, *args, **kwargs)
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

    def calcByteLen(self, text):
        return len(self.encoder(text)[0])

    def calcBytePos (self, text, pos):
        return len(self.encoder(text[:pos])[0])

    def calcCharPos(self, bytepos):
        if bytepos == 0:
            return 0
        try:
            return len(self.decoder(self.encoder(self.text)[0][:bytepos])[0])
        except (UnicodeDecodeError):
            self.calcCharPos(self.text, bytepos-1)

    def calcCharSpans(self, tokenbuttons):
        self.charspans = []
        startchar = 0
        charlength = 0
        for btn in tokenbuttons:
            token = btn.token.token
            charlength = len(token)
            tokenindex = self.text[startchar:].find(token)
            if tokenindex == -1:
                #FIXME: handle missing tokens properly
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
        self.intervals = IntervalTree()
        for btn, span in zip(tokenbuttons, charspans):
            start, length = span
            if length == 0:
                #FIXME: need to find better solution for the missing tokens
                length = 1
            self.intervals[start:start+length] = btn.GetId()

    def getButtonHere(self, pos):
        if pos == 0:
            return sorted(self.intervals)[0][2]
        try:
            return sorted(self.intervals[pos])[0][2]
        except (IndexError):
            return self.getButtonHere(pos-1)

    def SetSentence(self, text, tokenbuttons):
        self.text = text
        self.calcCharSpans(tokenbuttons)
        self.SetText(self.text)
        self.SetReadOnly(True)
        self.StartStyling(0, 0xff)
        self.SetStyling(self.calcByteLen(self.text), 0)
        self.DoColorSentence(tokenbuttons)

    def ClearSentence(self):
        self.charspans = []
        self.intervals = IntervalTree()
        self.SetReadOnly(False)
        self.ClearAll()
        
    def DoColorToken(self, btn):
        snum, toknum = btn.index
        token = btn.token.token
        try:
            startchar, charlength = self.charspans[toknum]
        except (IndexError):
            print toknum, token
        bytepos = self.calcBytePos(self.text, startchar)
        bytelen = self.calcByteLen(token)
        self.StartStyling(bytepos, 0xff)
        self.SetStyling(bytelen, btn.statecode)
        #self.GotoPos(bytepos+bytelen)
        self.Layout()

    def DoColorSentence(self, tokenbuttons):
        for btn in tokenbuttons:
            self.DoColorToken(btn)

    def OnSelectorUpdate(self, evt):
        btn = evt.GetEventObject()
        self.DoColorToken(btn)
        evt.Skip()

    def OnClick(self, evt):
        bytepos = self.GetCurrentPos()
        charpos = self.calcCharPos(bytepos)
        btn_id = self.getButtonHere(charpos)
        btnevt = ShowSelectorEvent(btn_id)
        wx.PostEvent(self.GetEventHandler(), btnevt)
        evt.Skip()

    def OnKeyPressed(self, evt):
        if evt.GetKeyCode() == wx.stc.STC_KEY_RETURN:
            self.OnClick(evt)
        evt.Skip()
    
    def OnTokenSplit(self, evt):
        snum, toknum = evt.index
        startchar, charlength = self.charspans[toknum]
        newtokens = u' '.join(evt.result)
        self.UpdateText(startchar, startchar+charlength, newtokens, snum)
        evt.Skip()

    def OnTokenJoin(self, evt):
        snum = evt.snum
        startfirst, lenfirst = self.charspans[evt.first]
        startsecond, lensecond = self.charspans[evt.second]
        first = self.text[startfirst:startfirst+lenfirst]
        second = self.text[startsecond:startsecond+lensecond]
        self.UpdateText(startfirst, startsecond+lensecond, u''.join((first, second)), snum)
        evt.Skip()

    def OnTokenEdit(self, evt):
        snum, toknum = evt.index
        startchar, charlength = self.charspans[toknum]
        senttoken = self.text[startchar:startchar+charlength]
        if not senttoken == evt.token:
            self.UpdateText(startchar, startchar+charlength, evt.token, snum)
        evt.Skip()

    def UpdateText(self, start, end, newtext, snum):
        self.text = ''.join([self.text[:start], newtext, self.text[end:]])
        sentevent = SentenceEditEvent(self.GetId(), snum=snum, sent=self.text)
        wx.PostEvent(self.GetEventHandler(), sentevent)

    def Highlight(self, start, end):
        pass


## PANELS

class FilePanel(wx.ScrolledWindow):
    'Text fileview panel'
    def __init__(self, parent, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.parent = parent

    def ShowFile(self, sentlist):
        Sizer = wx.BoxSizer(wx.VERTICAL)
        for n, sent in enumerate(sentlist):
            st = SentText(self, -1, num=n, style=wx.ST_NO_AUTORESIZE)
            st.SetLabel(sent)
            st.Wrap(self.GetClientSize().GetWidth()-20)
            st.Bind(wx.EVT_LEFT_DOWN, st.onMouseEvent)
            Sizer.Add(st, 1, wx.EXPAND)

        self.SetSizer(Sizer)
        self.Layout()


class SentPanel(wx.Panel):
    'Manual disambiguation panel'
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
        self.sentnumbutton = wx.SpinCtrl(self, wx.ID_ANY, "", (10,20), style=wx.TE_PROCESS_ENTER)
        self.sentnumbutton.SetRange(1, self.numsent)
        prevbutton = wx.Button(self, wx.ID_ANY, '<')
        prevbutton.Bind(wx.EVT_BUTTON, self.PrevSentence)
        nextbutton = wx.Button(self, wx.ID_ANY, '>')
        nextbutton.Bind(wx.EVT_BUTTON, self.NextSentence)
        savebutton = wx.Button(self, wx.ID_ANY, 'Save results')
        savebutton.Bind(wx.EVT_BUTTON, self.OnSaveResults)
        self.searchbutton = wx.SearchCtrl(self, size=(200,-1), style=wx.TE_PROCESS_ENTER)
        self.findprevbutton = wx.Button(self, wx.ID_ANY, '<Prev')
        self.findnextbutton = wx.Button(self, wx.ID_ANY, 'Next>')
        self.navsizer = wx.BoxSizer(wx.HORIZONTAL)
        sentenceno = wx.StaticText(self, wx.ID_ANY, "Sentence No")
        sentenceno.SetFont(self.sentfont)
        sentenceno.SetForegroundColour(self.sentcolor)
        self.navsizer.Add(sentenceno, 0)
        self.navsizer.Add(self.sentnumbutton)
        sentof = wx.StaticText(self, wx.ID_ANY, " of {}  ".format(self.numsent))
        sentof.SetFont(self.sentfont)
        sentof.SetForegroundColour(self.sentcolor)
        self.navsizer.Add(sentof, 0)
        self.navsizer.Add(prevbutton, 0)
        self.navsizer.Add(nextbutton, 0)
        self.navsizer.Add(savebutton, 0, wx.ALIGN_RIGHT)
        self.navsizer.Add(self.searchbutton, 0, wx.EXPAND)
        self.navsizer.Add(self.findprevbutton, 0)
        self.navsizer.Add(self.findnextbutton, 0)
        copybutton = wx.Button(self, wx.ID_COPY)
        copybutton.Bind(wx.EVT_BUTTON, self.OnCopyToClipboard)
        self.navsizer.Add(copybutton)
        self.sentsource = SentenceText(self)
        self.Sizer.Add(self.navsizer)
        self.Sizer.Add(self.sentsource, 0, wx.EXPAND)
        self.SetSizer(self.Sizer)
        self.Layout()

        # bind custom events
        self.Bind(EVT_SELECTOR_UPDATED, self.OnSelectorUpdate)
        self.Bind(EVT_SHOW_SELECTOR, self.OnShowSelector)
        self.Bind(EVT_TOKEN_EDIT, self.sentsource.OnTokenEdit)
        self.Bind(EVT_TOKEN_JOIN, self.sentsource.OnTokenJoin)
        self.Bind(EVT_TOKEN_SPLIT, self.sentsource.OnTokenSplit)

    def CreateGlossButtons(self):
        tokenbuttons = []
        self.annotlist = wx.lib.scrolledpanel.ScrolledPanel(self, wx.ID_ANY)
        self.annotlist.SetScrollRate(20, 20)
        if self.vertical:
            annotsizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            annotsizer = wx.BoxSizer(wx.VERTICAL) 
        for (toknum, (token,selectlist)) in enumerate(zip(self.tokenlist,self.selectlist)):
            abox = GlossSelector(self.annotlist, (self.snum, toknum), token, selectlist, vertical=self.vertical)
            tokenbuttons.append(abox)
            annotsizer.Add(abox)
        self.annotlist.SetSizer(annotsizer)
        self.annotlist.Layout()
        return tokenbuttons

    def ShowSent(self, senttuple, snum):
        self.senttext, self.selectlist, self.tokenlist, self.sentindex = senttuple
        self.senttext = self.senttext.strip()
        if self.isshown:
            self.sentsource.ClearSentence()
            self.Sizer.Remove(self.annotlist)
            self.annotlist.Destroy()
        self.snum = snum
        self.sentnumbutton.SetValue(snum+1)
        tokenbuttons = self.CreateGlossButtons()
        self.sentsource.SetSentence(self.senttext, tokenbuttons)
        self.Sizer.Add(self.annotlist, 1, wx.EXPAND)
        self.Layout()
        self.isshown = True

    def PrevSentence(self, event):
        self.OnSaveResults(event)
        if self.snum>0:
            prevsent = self.snum-1
        else:
            prevsent = len(self.GetTopLevelParent().processor.glosses)-1
        self.GetTopLevelParent().ShowSent(prevsent)

    def NextSentence(self, event):
        self.OnSaveResults(event)
        nextsent = self.snum+1
        try:
            self.GetTopLevelParent().ShowSent(nextsent)
        except IndexError:
            self.GetTopLevelParent().ShowSent(0)

    def OnSaveResults(self, event):
        evt = SaveResultsEvent(self.GetId())
        wx.PostEvent(self.GetEventHandler(), evt)

    def OnCopyToClipboard(self, evt):
        if self.senttext:
            clipdata = wx.TextDataObject()
            clipdata.SetText(self.senttext)
            if not wx.TheClipboard.IsOpened():
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(clipdata)
                wx.TheClipboard.Close()

    def OnSelectorUpdate(self, evt):
        self.sentsource.OnSelectorUpdate(evt)
        self.Layout()
        evt.Skip()

    def OnShowSelector(self, evt):
        btn_id = evt.GetId()
        btn = self.annotlist.FindWindowById(btn_id)
        self.annotlist.ScrollChildIntoView(btn)


class MainFrame(wx.Frame):
    'Main frame'
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

        filemenu= wx.Menu()
        recent = wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN,"O&pen"," Open text file")
        self.Bind(wx.EVT_MENU, self.OnMenuOpen, menuOpen)
        filemenu.AppendMenu(wx.ID_ANY, "Open &recent", recent)
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
        menuSave = filemenu.Append(wx.ID_SAVE,"S&ave"," Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSave, menuSave)
        menuSaveAs = filemenu.Append(wx.ID_SAVEAS,"S&ave as"," Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSaveAs, menuSaveAs)
        menuClose = filemenu.Append(wx.ID_CLOSE,"C&lose","Close current file")
        self.Bind(wx.EVT_MENU,self.OnClose, menuClose)
        menuSearch = filemenu.Append(wx.ID_FIND,"F&ind","Find text")
        self.Bind(wx.EVT_MENU, self.OnMenuSearch, menuSearch)
        menuExit = filemenu.Append(wx.ID_EXIT,"E&xit"," Terminate the program")
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File") # Adding the "filemenu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.
        
        settingsmenu = wx.Menu()
        menuVertical = settingsmenu.Append(wx.ID_ANY, "V&ertical", " Toggle horizontal/vertical display mode")
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
        menuBar.Append(settingsmenu,"&Settings")
        self.SetMenuBar(menuBar)

        debugmenu = wx.Menu()
        menuInspector = debugmenu.Append(wx.ID_ANY, "Widget I&nspector", "Widget Inspector")
        self.Bind(wx.EVT_MENU, self.OnWidgetInspector, menuInspector)
        menuBar.Append(debugmenu,"&Debug") 

        # Custom events
        self.Bind(EVT_SELECTOR_UPDATED, self.OnSelectorUpdate)
        self.Bind(EVT_SAVE_RESULTS, self.OnSave)
        self.Bind(EVT_TOKEN_SPLIT, self.OnTokenSplit)
        self.Bind(EVT_TOKEN_JOIN, self.OnTokenJoin)
        self.Bind(EVT_TOKEN_EDIT, self.OnTokenEdit)
        self.Bind(EVT_SENT_EDIT, self.OnSentenceEdit)
        self.Bind(EVT_LOCALDICT_LOOKUP, self.OnLocaldictLookup)
        self.Bind(EVT_LOCALDICT_SAVE, self.OnLocaldictSave)
        self.Bind(EVT_GLOSS_EDITED, self.OnGlossEdited)

        self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.Sizer)
        self.Show()

    def SetLocaldict(self, dictfile):
        if os.path.exists(dictfile):
            self.localdict = formats.DictReader(dictfile).get()
        else:
            self.localdict = formats.DabaDict()

    def InitValues(self):
        self.infile = None
        self.outfile = None
        self.processor = FileParser()
        self.searcher = SearchTool(self.processor)
        self.logger = None
        self.fileopened = False
        self.undolist = defaultdict(list)
        

    def InitUI(self):
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
        self.SetTitle("no file")
        self.notebook.Destroy()

    def UpdateUI(self):
        self.Freeze()
        try:
            snum = self.sentpanel.snum
        except (AttributeError):
            snum = None
        self.CleanUI()
        self.InitUI()
        if not snum is None:
            self.filepanel.ShowFile(t[0] for t in self.processor.glosses)
            self.ShowSent(snum)
        self.Layout()
        self.Thaw()

    def OnVerticalMode(self, e):
        self.config.WriteBool("display/vertical", not self.config.ReadBool("display/vertical"))
        self.config.Flush()
        if self.fileopened:
            self.UpdateUI()

    def OnSelectFont(self, e):
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
        dlg = StatusColorsDialog(self, self.config, self.statuscolors)
        if dlg.ShowModal() == wx.ID_OK:
            self.config.Flush()
        dlg.Destroy()

    def OnSetLocaldict(self, e):
        if not self.fileopened:
            self.NoFileError(e)
        else:
            dlg = wx.FileDialog(self, "Choose localdict file", self.dirname, "localdict.txt", "*.*", wx.OPEN)
            if dlg.ShowModal() == wx.ID_OK:
                dictfile = dlg.GetPath()
                self.SetLocaldict(dictfile)
                if not dictfile == '/'.join([self.dirname, "localdict.txt"]):
                    self.config.Write('/'.join(['localdict', self.infile]), dictfile)
                dlg.Destroy()

    def OnWidgetInspector(self, e):
        import wx.lib.inspection
        wx.lib.inspection.InspectionTool().Show()

    def OnSelectorUpdate(self, e):
        selector = e.GetEventObject()
        if selector.selectlist:
            self.processor.dirty = True
        token = selector.GetToken()
        snum, toknum = selector.index
        self.processor.glosses[snum][1][toknum] = selector.selectlist
        self.processor.glosses[snum][2][toknum] = token

    def ShowSent(self, snum):
        if self.undolist[snum]:
            self.menuUndoTokens.Enable(True)
        self.SaveFilePos(snum)
        self.sentpanel.ShowSent(self.processor.glosses[snum], snum)

    def OnTokenSplit(self, evt):
        snum, toknum = evt.index
        savedtoken = self.processor.glosses[snum][2][toknum]
        edit = TokenEdit('split', toknum, toknum+len(evt.result), [savedtoken])
        self.undolist[snum].append(edit)
        del self.processor.glosses[snum][1][toknum]
        del self.processor.glosses[snum][2][toknum]
        shift = 0
        for token in evt.result:
            self.processor.glosses[snum][1].insert(toknum+shift, [])
            self.processor.glosses[snum][2].insert(toknum+shift, formats.GlossToken(('w', (token, '-1', [Gloss(token, (), '', ())]))))
            shift = shift+1
        self.processor.dirty = True
        wx.CallAfter(self.ShowSent, snum)

    def OnTokenJoin(self, evt):
        snum = evt.snum
        first = evt.first
        second = evt.second
        savedtokens = self.processor.glosses[snum][2][first:second+1]
        edit = TokenEdit('join', first, second, savedtokens)
        self.undolist[snum].append(edit)
        firsttoken = self.processor.glosses[snum][2][first]
        nexttoken = self.processor.glosses[snum][2][second]
        #FIXME: will break on non-word tokens
        newform = firsttoken.token + nexttoken.token
        newtoken = formats.GlossToken(('w', (newform, '-1', [Gloss(newform, (),'',())])))
        self.processor.glosses[snum][1][first] = []
        del self.processor.glosses[snum][1][second]
        self.processor.glosses[snum][2][first] = newtoken
        del self.processor.glosses[snum][2][second]
        self.processor.dirty = True
        wx.CallAfter(self.ShowSent, snum)

    def OnTokenEdit(self, evt):
        snum, toknum = evt.index
        savedtoken = self.processor.glosses[snum][2][toknum]
        if evt.toktype == 'w':
            if savedtoken.type == 'w':
                newtoken = savedtoken
                newtoken.token = evt.token
            else:
                newtoken = formats.GlossToken(('w', (evt.token, '-1', [Gloss(evt.token, (), '', ())])))
        else:
            newtoken = formats.GlossToken((evt.toktype, evt.token))
        self.processor.glosses[snum][2][toknum] = newtoken
        self.processor.dirty = True
        wx.CallAfter(self.ShowSent, snum)

    def OnSentenceEdit(self, evt):
        savedsent = self.processor.glosses[evt.snum]
        self.processor.glosses[evt.snum] = (evt.sent,) + savedsent[1:]
        self.processor.dirty = True

    def OnGlossEdited(self, evt):
        self.processor.dirty = True
    
    def OnLocaldictLookup(self, evt):
        try:
            savedglosses = self.localdict[evt.gloss.form]
            dlg = evt.dlg
            wx.CallAfter(dlg.ShowLocaldictVariants, savedglosses)
        except (KeyError):
            pass

    def OnLocaldictSave(self, evt):
        gloss = evt.gloss
        # we do not save words with empty glosses into localdict
        if not gloss.gloss:
            return
        if gloss.form in self.localdict:
            if gloss not in self.localdict[gloss.form]:
                self.localdict[gloss.form].insert(0, gloss)
        else:
            self.localdict[gloss.form] = gloss
    
    def OnUndoTokens(self,e):
        snum = self.sentpanel.snum
        if self.undolist[snum]:
            savedstate = self.undolist[snum].pop()
            if savedstate.operation == 'split':
                self.processor.glosses[snum][2][savedstate.start:savedstate.end+1] = savedstate.toklist
            elif savedstate.operation == 'join':
                self.processor.glosses[snum][2][savedstate.start:savedstate.end] = savedstate.toklist
            else:
                print "Unimplemented undo operation!"
            self.ShowSent(snum)

    def OnMenuSearch(self,e):
        dlg = SearchDialog(self, wx.ID_ANY, "Search word or sentence part", "")
        if (dlg.ShowModal() == wx.ID_OK):
            searchstr = dlg.GetSearchString()
            self.DoSearch(searchstr)

    def OnButtonSearch(self,e):
        searchstr = self.sentpanel.searchbutton.GetValue()
        self.DoSearch(searchstr)

    def DoSearch(self, searchstr):
        if not searchstr:
            return
        # search forward by default
        firstmatch = self.searcher.find(searchstr, startsent=self.sentpanel.snum)
        self.ShowSearchResult(firstmatch)

    def ShowSearchResult(self, match):
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
        match = self.searcher.findPrev()
        self.ShowSearchResult(match)

    def OnFindNext(self, e):
        match = self.searcher.findNext()
        self.ShowSearchResult(match)

    def OnGotoSentence(self, e):
        self.sentpanel.OnSaveResults(e)
        snum = self.sentpanel.sentnumbutton.GetValue() - 1
        self.ShowSent(snum)

    def SaveFilePos(self, snum):
        if self.fileopened:
            self.config.WriteInt(self.infile, snum)
            self.config.Flush()

    def GetFilePos(self, filename):
        snum = self.config.ReadInt(filename, 0)
        return snum

    def OnClose(self,e):
        if self.fileopened:
            if self.processor.dirty:
                self.OnSave(e)
            if self.logger:
                self.logger.OnExit()
            self.InitValues()
            self.CleanUI()

    def OnExit(self,e):
        if self.fileopened:
            self.OnClose(e)
        self.Close(True)

    def NoFileError(self,e):
        dlg = wx.MessageDialog(self, 'Error: no file opened!', 'No file opened', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def FileOpenedError(self,e):
        dlg = wx.MessageDialog(self, 'Error: previous file not closed!', 'Previous file is still opened. You should close it before opening the next one', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnMenuOpen(self,e):
        if self.fileopened:
            self.FileOpenedError(e)
        else:
            dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
            if dlg.ShowModal() == wx.ID_OK:
                self.DoOpen(dlg.GetPath())
                dlg.Destroy()

    def OnFileHistory(self,e):
        if self.fileopened:
            self.FileOpenedError(e)
        else:
            filenum = e.GetId() - wx.ID_FILE1
            self.DoOpen(self.filehistory.GetHistoryFile(filenum))

    def DoOpen(self,filename):
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
        self.filepanel.ShowFile(t[0] for t in self.processor.glosses)
        snum = self.GetFilePos(self.infile)
        self.ShowSent(snum)
        self.fileopened = True
        self.Layout()

    def SaveFiles(self):
        if self.localdict:
            formats.DictWriter(self.localdict, self.dictfile, lang='default', name='localdict',ver='0').write()
        self.processor.write(self.outfile)
        self.config.Flush()

    def OnSave(self,e):
        if not self.fileopened:
            self.NoFileError(e)
        else:
            if not self.outfile:
                self.OnSaveAs(e)
            else:
                self.SaveFiles()

    def OnSaveAs(self,e):
        if not self.fileopened:
            self.NoFileError(e)
        else:
            xfilename = ''.join(['.'.join([get_basename(self.infile), 'dis']), os.path.extsep, 'html'])

            dlg = wx.FileDialog(self, "Choose a file", os.path.dirname(self.infile), xfilename, "*.html", wx.SAVE)
            if dlg.ShowModal() == wx.ID_OK:
                self.outfile = dlg.GetPath()
                if not os.path.splitext(self.outfile)[1] == '.html' :
                    self.outfile = ''.join([self.outfile, os.path.extsep, 'html'])
                self.SaveFiles()
                self.filehistory.AddFileToHistory(self.outfile)
            dlg.Destroy()


if __name__ == '__main__':
    app = wx.App()
    frame = MainFrame(None, title="Daba disambiguation interface (GUI)")
    frame.Show()
    app.MainLoop()

