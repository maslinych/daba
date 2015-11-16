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

import wx
import wx.stc
import wx.lib.scrolledpanel as scrolled
import wx.combo
import wx.lib.newevent
from wx.lib.stattext import GenStaticText
import os
import formats
import datetime
import codecs
import unicodedata
import platform
import xml.etree.cElementTree as e
from ntgloss import Gloss, emptyGloss
import grammar
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError
from intervaltree import Interval, IntervalTree

## EVENTS 

GlossSelectorEvent, EVT_SELECTOR_UPDATED = wx.lib.newevent.NewCommandEvent()
GlossButtonEvent, EVT_GLOSS_SELECTED = wx.lib.newevent.NewCommandEvent()
GlossEditButtonEvent, EVT_GLOSS_EDITED = wx.lib.newevent.NewCommandEvent()
ShowSelectorEvent, EVT_SHOW_SELECTOR = wx.lib.newevent.NewCommandEvent()
SaveResultsEvent, EVT_SAVE_RESULTS = wx.lib.newevent.NewCommandEvent()


## UTILITY functions and no-interface classes

normalizeText = lambda t: unicodedata.normalize('NFKD', unicode(t))

def get_basename(fname):
    basename = os.path.splitext(fname)[0]
    pars = basename.rfind('.pars')
    if pars > 0:
        return basename[:pars]
    #FIXME: may occasionally cut off part of filename
    dis = basename.rfind('.dis')
    if dis > 0 and len(basename)-dis <= 7:
        return basename[:dis]
    return basename

class NormalizedTextCtrl(wx.TextCtrl):
    def __init__(*args, **kwargs):
        if len(args)>3:
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
            for snum,sent in enumerate(par):
                # tuple(sent_text, selectlist, glosslist, index)
                self.glosses.append((sent[0], [[] for i in sent[1]], sent[1], (pnum,snum)))
                self.numsent = freader.numsent
                self.numwords = freader.numwords

    def write(self, filename):
        out = [[]]
        for sent in self.glosses:
            pnum = sent[3][0]
            if pnum>len(out)-1:
                out.append([])
            outgloss = []
            for selectlist,glosstoken in zip(sent[1], sent[2]):
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
            self.GetTopLevelParent().sentpanel.ShowSent(self.GetTopLevelParent().processor.glosses[self.num], self.num)
            self.GetTopLevelParent().Layout()

        event.Skip()



class GlossButton(wx.Panel):
    def __init__(self, parent, gloss, disabled=False, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.selected = False
        self.children = []
        self.gloss = gloss
        self.disabled = disabled

        box = wx.BoxSizer(wx.VERTICAL)
        # prepare main gloss button
        if self.disabled:
            self.main = wx.Button(self, -1, makeGlossString(gloss))
            self.main.Disable()
        else:
            self.main = wx.ToggleButton(self, -1, makeGlossString(gloss))
            self.main.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggled)
        self.main.SetBackgroundColour('White')
        box.Add(self.main, 0,wx.EXPAND)
        # prepare morphemes buttons recursively
        if gloss.morphemes:
            morphemes = wx.BoxSizer(wx.HORIZONTAL)
            for morph in gloss.morphemes:
                m = GlossButton(self, morph, disabled=self.disabled)
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
            self.main.SetForegroundColour("DarkGreen")
        else:
            self.main.SetForegroundColour("Black")
        self.ToggleChildren()
 
    def ToggleChildren(self):
        for child in self.children:
            if bool(child.main.GetValue()) != self.selected:
                child.main.SetValue(self.selected)
                child.DoToggle()


class GlossInputDialog(wx.Dialog):
    def __init__(self, parent, id, title, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)
        self.as_gloss = emptyGloss
        self.morphemes = []
        self.parent = parent
        self.freeze = False

        vbox_top = wx.BoxSizer(wx.VERTICAL)
        vbox_top.Add(wx.StaticText(self, -1, "Gloss string (edit inplace):"))
        self.glosstext = NormalizedTextCtrl(self, -1)
        vbox_top.Add(self.glosstext, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)
        self.gbutton = GlossButton(self, self.as_gloss, disabled=True)
        vbox_top.Add(self.gbutton)
        cb = wx.CheckBox(self, -1, "Save to localdict")
        vbox_top.Add(cb, 0, wx.TOP | wx.BOTTOM, 10)

        cb.Bind(wx.EVT_CHECKBOX, self.OnCheckLocaldict)
        self.glosstext.Bind(wx.EVT_TEXT, self.OnEditGlosstext)

        vbox_top.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(vbox_top)
        self.Fit()
        self.Layout()

        self.localdict = self.parent.GetTopLevelParent().localdict
        self.fromlocaldict = False
        self.save = True
        cb.SetValue(True)


    def SetGloss(self, gloss):
        self.as_gloss = gloss
        self.UpdateInterface(gloss)

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
        self.gbutton = GlossButton(self, gloss, disabled=True)
        sizer.Insert(2, self.gbutton)
        self.FitGlosstextWidth()
        self.freeze = False
     
    def SetGlossAttr(self, **kwargs):
        self.as_gloss._replace(**kwargs) 

    def GetGloss(self):
        return self.as_gloss

    def OnEditGlosstext(self, evt):
        if not self.freeze:
            self.FitGlosstextWidth()
            glosstext = self.glosstext.GetValue()
            oldgloss = self.as_gloss
            try:
                toks = grammar.str_tokenize(glosstext)
                self.as_gloss = grammar.stringgloss_parser().parse(toks)
                if not self.as_gloss == oldgloss:
                    self.glosstext.SetBackgroundColour(wx.NullColour)
                    self.UpdateInterface(self.as_gloss)
                    self.parent.GetTopLevelParent().processor.dirty = True
                else:
                    self.glosstext.SetBackgroundColour('yellow')

            except (LexerError, NoParseError) as e:
                self.glosstext.SetBackgroundColour('yellow')

    def OnCheckLocaldict(self, evt):
        self.save = not self.save

    def SaveGloss(self):
        #FIXME: homonymous forms will only save last
        if self.save:
            gloss = self.GetGloss()
            if gloss.form in self.localdict:
                if gloss not in self.localdict[gloss.form]:
                    self.localdict[gloss.form].insert(0, gloss)
            else:
                self.localdict[gloss.form] = gloss


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
            self.splittext = wx.StaticText(self, -1, ' | '.join(self.split))
            sizer.Insert(2, self.splittext, 0, wx.EXPAND)
            self.Layout()
    
    def GetResult(self):
        return self.split

class GlossEditButton(wx.Panel):
    def __init__(self, parent, gloss, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.gloss = gloss
        self.state = None
        self.button = wx.Button(self, -1, makeGlossString(gloss, morphemes=True), style=wx.NO_BORDER)
        sizer.Add(self.button,0)

        self.SetSizer(sizer)
        self.button.Bind(wx.EVT_BUTTON, self.OnEditGloss)
        self.parent = parent #FIXME: find a better way to reference GlossSelector
        self.statecolours = {
                1: 'Black',
                2: 'Navy',
                3: 'Blue',
                4: 'Red',
                5: 'Green'
                }
        
    def OnEditGloss(self, event):
        dlg = GlossInputDialog(self, -1, 'Insert gloss manually')
        localdict = self.GetTopLevelParent().localdict
        try:
            dlg.SetGloss(localdict[self.gloss.form][0])
        except KeyError:
            dlg.SetGloss(self.gloss)

        if (dlg.ShowModal() == wx.ID_OK):
            dlg.SaveGloss()
            newgloss = dlg.GetGloss()
            self.gloss = newgloss
            self.parent.OnEdition(newgloss)
        dlg.Destroy()

    def OnStateChange(self, statecode, gloss):
        glossstring = makeGlossString(gloss, morphemes=True)
        self.button.SetLabel(glossstring)
        self.Layout()
        try:
            self.button.SetForegroundColour(self.statecolours[statecode])
            self.state = statecode
        except KeyError:
            #FIXME: proper error message
            print 'Unknown state code:', statecode


class GlossSelector(wx.Panel):
    def __init__(self, parent, index, glosstoken, selectlist, vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        try:
            self.toktype, (self.form, self.stage, self.glosslist) = glosstoken.as_tuple()
            self.token = glosstoken
        except ValueError:
            print glosstoken
        self.selectlist = selectlist
        self.vertical = vertical
        self.mbutton = None
        self.parent = parent
        self.children = []
        self.parserstage = self.stage
        self.index = index
        self.logger = self.GetTopLevelParent().logger

        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(EVT_GLOSS_SELECTED, self.OnGlossSelected)

        if self.vertical:
            self.sizer = wx.BoxSizer(wx.VERTICAL)
        else:
            self.sizer = wx.BoxSizer(wx.HORIZONTAL) 


        #FIXME: should I keep token string and use it here in spite of glosslist's first form?
        if len(self.glosslist) > 1:
            self.gloss = Gloss(self.form, (), '', ())
            self.statecode = 2
        elif ''.join(self.glosslist[0].ps) in ['', None, '<?>'] and self.glosslist[0].gloss in ['', None, '<?>'] and not self.glosslist[0].morphemes:
            self.gloss = Gloss(self.glosslist[0].form, (), '', ())
            self.statecode = 4
        else:
            self.gloss = self.glosslist[0]
            self.statecode = 1
        
        self.UpdateState(self.statecode, self.gloss)

        self.sizerflags = (wx.EXPAND | wx.TOP | wx.BOTTOM, 4)
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

    def AddButtons(self, glosslist):
        if len(self.glosslist) > 1:
            for gloss in glosslist:
                gbutton = GlossButton(self, gloss)
                self.children.append(gbutton)
                self.sizer.Add(gbutton, 0, *self.sizerflags)
            self.SetSizer(self.sizer)
            self.Layout()

    def UpdateState(self, statecode, gloss):
        if not self.mbutton:
            self.mbutton = GlossEditButton(self, self.gloss)
        self.mbutton.OnStateChange(self.statecode, self.gloss)

    def OnEdition(self, gloss):
        oldgloss = self.gloss
        self.gloss = gloss
        self.glosslist = [gloss] + [button.gloss for button in self.children]
        selectedbuttons = [button.gloss for button in self.children if button.selected]
        if selectedbuttons:
            self.selectlist = [gloss] + selectedbuttons
        else:
            self.selectlist = [gloss]
        self.statecode = 5
        self.UpdateState(self.statecode, self.gloss)
        self.OnSelectorUpdated()
        self.logger.LogEdit(oldgloss, self.gloss)

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

    def JoinTwo(self, first, second):
        glosses = self.GetTopLevelParent().processor.glosses
        sentpanel = self.GetTopLevelParent().sentpanel
        sentstate = glosses[sentpanel.snum]
        sentpanel.savedstate = tuple([sentstate[0], [i[:] for i in sentstate[1]], sentstate[2][:], sentstate[3]])

        firsttoken = glosses[sentpanel.snum][2][first]
        nexttoken = glosses[sentpanel.snum][2][second]
        #FIXME: will break on non-word tokens
        newform = firsttoken.token + nexttoken.token
        newtoken = formats.GlossToken(('w', (newform, '-1', [Gloss(newform, (),'',())])))
        sentstate[1][first] = []
        del sentstate[1][second]
        sentstate[2][first] = newtoken
        del sentstate[2][second]
        sentpanel.ShowSent(sentstate, sentpanel.snum)
        self.logger.LogJoin((firsttoken.token,nexttoken.token), newform)

    def OnJoinForward(self, evt):
        self.JoinTwo(self.index, self.index+1)

    def OnJoinBackward(self, evt):
        self.JoinTwo(self.index-1, self.index)

    def OnSplitToken(self, evt):
        dlg = TokenSplitDialog(self,self.form)
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.GetResult()
            if len(result) > 1:
                glosses = self.GetTopLevelParent().processor.glosses
                sentpanel = self.GetTopLevelParent().sentpanel
                sentstate = glosses[sentpanel.snum]
                sentpanel.savedstate = tuple([sentstate[0], [i[:] for i in sentstate[1]], sentstate[2][:], sentstate[3]])

                del sentstate[1][self.index]
                del sentstate[2][self.index]
                shift = 0
                for token in result:
                    sentstate[1].insert(self.index+shift, [])
                    sentstate[2].insert(self.index+shift, formats.GlossToken(('w', (token, '-1', [Gloss(token, (), '', ())]))))
                    shift = shift+1
                sentpanel.ShowSent(sentstate, sentpanel.snum)
                self.logger.LogSplit(self.form, result)

    def OnChangeTokenType(self, evt):
        pass


class TokenInputDialog(wx.Dialog):
    def __init__(self, parent, id, title, glosstoken, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)
        self.typedict = dict([("Comment", "Comment"), ("Punctuation", "c"), ("Markup", "Tag")])

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.tokenfield = NormalizedTextCtrl(self, -1, glosstoken.token)
        sizer.Add(self.tokenfield)
        self.typefield = wx.RadioBox(self, -1, "Token type", wx.DefaultPosition, wx.DefaultSize, self.typedict.keys(), 1)
        self.typefield.SetStringSelection(dict((v,k) for k,v in self.typedict.items())[glosstoken.type])
        sizer.Add(self.typefield)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)

    def GetToken(self):
        return formats.GlossToken((self.typedict[self.typefield.GetStringSelection()], self.tokenfield.GetValue()))

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

class TokenEditButton(wx.Panel):
    def __init__(self, parent, index, token, selectlist, vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.statecode = 0
        self.index = index
        self.selectlist = selectlist
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.token = token
        self.button = wx.Button(self, -1, self.token.token, style=wx.NO_BORDER)
        sizer.Add(self.button,0)
        self.SetSizer(sizer)
        self.button.Bind(wx.EVT_BUTTON, self.OnEditToken)

    def OnEditToken(self, event):
        dlg = TokenInputDialog(self, -1, 'Edit token', self.token)
        if (dlg.ShowModal() == wx.ID_OK):
            self.token = dlg.GetToken()
            self.button.SetLabel(self.token.token)
            self.selectlist = [self.token.as_tuple()]
            self.statecode = 5
        dlg.Destroy()

    def GetToken(self):
        return self.token


class SentenceText(wx.stc.StyledTextCtrl):
    def __init__(self, parent, *args, **kwargs):
        wx.stc.StyledTextCtrl.__init__(self, parent, *args, **kwargs)
        self.encoder = codecs.getencoder("utf-8")
        self.decoder = codecs.getdecoder("utf-8")
        # defining styles
        pb = 16
        if platform.system() == 'Windows':
            face = 'Arial'
        else:
            face = 'Helvetica'
        self.style_default = 0
        self.style_unambiguous = 1
        self.style_ambiguous = 2
        self.style_uncertain = 3
        self.style_unparsed = 4
        self.style_manual = 5

        self.StyleSetSpec(wx.stc.STC_STYLE_DEFAULT, "size:%d,face:%s,back:#FFFFFF,fore:#1A4780" % (pb, face))
        self.StyleClearAll()
        self.StyleSetSpec(self.style_unambiguous, "size:%d,face:%s,bold,back:#FFFFFF,fore:#1A4780" % (pb, face))
        self.StyleSetSpec(self.style_ambiguous, "size:%d,face:%s,back:#cccccc,fore:#1A4780" % (pb, face))
        self.StyleSetSpec(self.style_uncertain, "size:%d,face:%s,back:#dda0dd,fore:#1A4780" % (pb, face))
        self.StyleSetSpec(self.style_unparsed, "size:%d,face:%s,back:#fc6c85,fore:#1A4780" % (pb, face))
        self.StyleSetSpec(self.style_manual, "size:%d,face:%s,back:#0bda51,fore:#1A4780" % (pb, face))
        self.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.Layout()

        # FIXME: finish it
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
            tokenindex = self.text[startchar:].find(token)+startchar
            if tokenindex == -1:
                #FIXME: handle missing tokens properly
                print "NOT FOUND IN THE SENTENCE:", token
                tokenindex = startchar
            charspan = (tokenindex, charlength)
            startchar = tokenindex+charlength
            self.charspans.append(charspan)
        self.calcButtonIntervals(tokenbuttons, self.charspans)
        return self.charspans

    def calcButtonIntervals(self, tokenbuttons, charspans):
        self.intervals = IntervalTree()
        for btn, span in zip(tokenbuttons, charspans):
            start, length = span
            self.intervals[start:start+length] = btn

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
        btn = self.getButtonHere(charpos)
        btnevt = ShowSelectorEvent(btn.GetId())
        btnevt.SetEventObject(btn)
        wx.PostEvent(btn.GetEventHandler(), btnevt)
        evt.Skip()

    def OnKeyPressed(self, evt):
        if evt.GetKeyCode() == wx.stc.STC_KEY_RETURN:
            self.OnClick(evt)
        evt.Skip()


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

        # bind disambiguation events
        self.Bind(EVT_SELECTOR_UPDATED, self.OnSelectorUpdate)
        self.Bind(EVT_SHOW_SELECTOR, self.OnShowSelector)

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

    def CreateGlossButtons(self):
        self.tokenbuttons = []
        self.annotlist = wx.lib.scrolledpanel.ScrolledPanel(self, wx.ID_ANY)
        self.annotlist.SetScrollRate(20, 20)
        if self.vertical:
            annotsizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            annotsizer = wx.BoxSizer(wx.VERTICAL) 
        for (toknum, (token,selectlist)) in enumerate(zip(self.tokenlist,self.selectlist)):
            if token.type == 'w':
                abox = GlossSelector(self.annotlist, (self.snum, toknum), token, selectlist, vertical=self.vertical)
            else:
                abox = TokenEditButton(self.annotlist, (self.snum, toknum), token, selectlist, vertical=self.vertical)
            self.tokenbuttons.append(abox)
            annotsizer.Add(abox)
        self.annotlist.SetSizer(annotsizer)
        self.annotlist.Layout()
        return self.annotlist

    def ShowSent(self, senttuple, snum):
        self.senttext, self.selectlist, self.tokenlist, self.sentindex = senttuple
        self.senttext = self.senttext.strip()
        if self.isshown:
            self.sentsource.ClearSentence()
            self.Sizer.Remove(self.annotlist)
            self.annotlist.Destroy()
        self.snum = snum
        self.sentnumbutton.SetValue(snum+1)
        self.GetTopLevelParent().SaveFilePos(snum)
        self.CreateGlossButtons()
        self.sentsource.SetSentence(self.senttext, self.tokenbuttons)
        self.Sizer.Add(self.annotlist, 1, wx.EXPAND)
        self.Layout()
        self.isshown = True

    def PrevSentence(self, event):
        self.OnSaveResults(event)
        if self.snum>0:
            prevsent = self.snum-1
        else:
            prevsent = len(self.GetTopLevelParent().processor.glosses)-1
        self.ShowSent(self.GetTopLevelParent().processor.glosses[prevsent], prevsent)
        self.GetTopLevelParent().Layout()

    def NextSentence(self, event):
        self.OnSaveResults(event)
        nextsent = self.snum+1
        try:
            self.ShowSent(self.GetTopLevelParent().processor.glosses[nextsent],nextsent)
        except IndexError:
            self.ShowSent(self.GetTopLevelParent().processor.glosses[0], 0)
        self.GetTopLevelParent().Layout()

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
        btn = evt.GetEventObject()
        self.annotlist.ScrollChildIntoView(btn)

class MainFrame(wx.Frame):
    'Main frame'
    def __init__(self, parent, *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)

        # constants, no need to reinit on opening next file
        self.config = wx.Config("gdisamb", style=wx.CONFIG_USE_LOCAL_FILE)
        self.dirname = self.config.Read("state/curdir", os.curdir)
        self.dictfile = 'localdict.txt'
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
        menuUndoTokens = settingsmenu.Append(wx.ID_ANY, "U&ndo join/split tokens", "Undo join/split tokens")
        self.Bind(wx.EVT_MENU, self.OnVerticalMode, menuVertical)
        self.Bind(wx.EVT_MENU, self.OnUndoTokens, menuUndoTokens)
        menuFont = settingsmenu.Append(wx.ID_ANY, "Select F&ont", "Select font")
        self.Bind(wx.EVT_MENU, self.OnSelectFont, menuFont)
        menuBar.Append(settingsmenu,"&Settings") 
        self.SetMenuBar(menuBar)  

        debugmenu = wx.Menu()
        menuInspector = debugmenu.Append(wx.ID_ANY, "Widget I&nspector", "Widget Inspector")
        self.Bind(wx.EVT_MENU, self.OnWidgetInspector, menuInspector)
        menuBar.Append(debugmenu,"&Debug") 

        # Custom events
        self.Bind(EVT_SELECTOR_UPDATED, self.OnSelectorUpdate)
        self.Bind(EVT_SAVE_RESULTS, self.OnSaveResults)

        #FIXME: loading localdict right on start, should give user possibility to choose
        if os.path.exists(self.dictfile):
            self.localdict = formats.DictReader(self.dictfile).get()
        else:
            self.localdict = formats.DabaDict()

        self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.Sizer)
        self.Show()

    def InitValues(self):
        self.infile = None
        self.outfile = None
        self.processor = FileParser()
        self.searcher = SearchTool(self.processor)
        self.logger = None
        self.fileopened = False

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
            self.sentpanel.ShowSent(self.processor.glosses[snum], snum)
        self.Layout()
        self.Thaw()

    def OnVerticalMode(self,e):
        self.config.WriteBool("display/vertical", not self.config.ReadBool("display/vertical"))
        self.config.Flush()
        if self.fileopened:
            self.UpdateUI()

    def OnSelectFont(self,e):
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
        print "UPDATING TOKEN", token.as_tuple(), "SELECTED:", selector.selectlist

    def OnSaveResults(self,e):
        print "Call to save results"

    def OnUndoTokens(self,e):
        savedstate = self.sentpanel.savedstate
        if savedstate:
            snum = self.sentpanel.snum
            self.processor.glosses[snum] = savedstate
            self.sentpanel.ShowSent(savedstate, snum)
            savedstate = None
        else:
            print "No undo information"

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
                self.sentpanel.ShowSent(self.processor.glosses[snum], snum)
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
        self.sentpanel.ShowSent(self.processor.glosses[snum], snum)

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
        self.logger = EditLogger(logfile)
        self.processor.read_file(self.infile)
        self.InitUI()
        self.SetTitle(self.filename)
        self.filepanel.ShowFile(t[0] for t in self.processor.glosses)
        snum = self.GetFilePos(self.infile)
        self.sentpanel.ShowSent(self.processor.glosses[snum], snum)
        self.fileopened = True
        self.Layout()

    def SaveFiles(self,e):
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
                self.SaveFiles(e)

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
                self.SaveFiles(e)
            dlg.Destroy()


if __name__ == '__main__':
    app = wx.App()
    frame = MainFrame(None, title="Daba disambiguation interface (GUI)")
    frame.Show()
    app.MainLoop()

