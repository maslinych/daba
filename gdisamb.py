#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Manual disambiguation editor
#
# Copyright (C) 2010  Kirill Maslinsky <kirill@altlinux.org>
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
import wx.lib.scrolledpanel as scrolled
from wx.lib.stattext import GenStaticText
import os
import formats
import xml.etree.cElementTree as e
from ntgloss import Gloss
from pytrie import StringTrie as trie

PSLIST = [
        'n.prop',
        'n',
        'adj',
        'num',
        'v',
        'ptcp',
        'vq',
        'adv',
        'onomat',
        'intj',
        'conj',
        'prt',
        'cop',
        'dtm',
        'pers',
        'pm',
        'pp',
        'prn',
        'PUNCT',
        ]

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
                    outgloss.append((glosstoken[0], (glosstoken[1][0], glosstoken[1][1], selectlist)))
            out[-1].append((sent[0], outgloss))
        fwriter = formats.HtmlWriter((self.metadata, out), filename)
        fwriter.write()



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
    def __init__(self, parent, gloss, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.selected = False
        self.children = []
        self.parent = parent
        self.gloss = gloss

        box = wx.BoxSizer(wx.VERTICAL)
        # prepare main gloss button
        self.main = wx.ToggleButton(self, -1, makeGlossString(gloss))
        self.main.SetBackgroundColour('White')
        self.main.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggled)
        box.Add(self.main, 0,wx.EXPAND)
        # prepare morphemes buttons recursively
        if gloss.morphemes:
            morphemes = wx.BoxSizer(wx.HORIZONTAL)
            for morph in gloss.morphemes:
                m = GlossButton(self, morph)
                self.children.append(m)
                morphemes.Add(m, 0)
            box.Add(morphemes, 0)

        self.SetSizer(box)

    def OnToggled(self, event):
        self.selected = not self.selected
        self.parent.OnSelection(self.gloss)
        if self.selected:
            self.main.SetForegroundColour("DarkGreen")
        else:
            self.main.SetForegroundColour("Black")
        for child in self.children:
            if bool(child.main.GetValue()) != self.selected:
                child.main.SetValue(self.selected)
                child.OnToggled(event)

    def OnSelection(self, gloss):
        #FIXME: HACK for recursive (morpheme) buttons, should instead 
        # do proper referencing to parent GlossSelector widget
        pass

class GlossInputDialog(wx.Dialog):
    def __init__(self, parent, id, title, *args, **kwargs):
        wx.Dialog.__init__(self, parent, id, title, *args, **kwargs)
        self.morphemes = []
        self.parent = parent

        vbox_top = wx.BoxSizer(wx.VERTICAL)
        grid = wx.GridBagSizer(2,2)
        grid.Add(wx.StaticText(self, -1, 'Form:'), (0,0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.form = wx.TextCtrl(self, -1)
        grid.Add(self.form, (0,1), flag=wx.EXPAND)
        self.ps = wx.CheckListBox(self, -1, choices=PSLIST)
        grid.Add(self.ps, (0,2), (3,1),  flag=wx.EXPAND)
        grid.Add(wx.StaticText(self, -1, 'Gloss:'), (1,0), flag=wx.ALIGN_TOP)
        self.gloss = wx.TextCtrl(self, -1)
        grid.Add(self.gloss, (1,1))
        addb = wx.Button(self, -1, 'Add morpheme')
        grid.Add(addb, (2,1), flag=wx.EXPAND)
        vbox_top.Add(grid, 0, wx.TOP | wx.BOTTOM, 10)
        cb = wx.CheckBox(self, -1, "Save to localdict")
        vbox_top.Add(cb, 0, wx.TOP | wx.BOTTOM, 10)

        cb.Bind(wx.EVT_CHECKBOX, self.OnCheckLocaldict)
        addb.Bind(wx.EVT_BUTTON, self.OnAddMorpheme)
        self.form.Bind(wx.EVT_TEXT, self.OnEditForm)

        vbox_top.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0)
        self.SetSizer(vbox_top)

        self.localdict = self.parent.GetTopLevelParent().localdict
        self.save = True
        cb.SetValue(True)

    def SetGloss(self, gloss):
        if not gloss.form == self.form.GetValue():
            self.form.SetValue(gloss.form)
        self.ps.SetCheckedStrings(gloss.ps)
        self.gloss.SetValue(gloss.gloss)

    def GetGloss(self):
        form = self.form.GetValue()
        ps = set(self.ps.GetCheckedStrings())
        gloss = self.gloss.GetValue()
        morphemes = tuple(self.morphemes)
        return Gloss(form, ps, gloss, morphemes)

    def OnEditForm(self, evt):
        newform = evt.GetString()
        if newform in self.localdict:
            self.SetGloss(self.localdict[newform][0])
            self.key = newform
    
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
                self.localdict[gloss.form] = [gloss]

    def OnAddMorpheme(self, event):
        if PSLIST[0] is not 'mrph':
            PSLIST.insert(0, 'mrph')
        dlg = GlossInputDialog(self.GetParent(), -1, "Add morpheme", pos=map(lambda x: x+20, self.GetPositionTuple()) )
        if (dlg.ShowModal() == wx.ID_OK):
            self.morphemes.append(dlg.GetGloss())


class TokenSplitDialog(wx.Dialog):
    def __init__(self, parent, form, *args, **kwargs):
        wx.Dialog.__init__(self, parent, -1, "Split gloss")
        self.form = form
        self.split = (self.form,)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(wx.StaticText(self, -1, "Move cursor to the split point:"))
        self.formfield = wx.TextCtrl(self, -1, self.form)
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
                -1: 'Red',
                0: 'Green'
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
        self.parent.Layout()
        self.parent.parent.Layout()
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
            self.toktype, (self.form, self.stage, self.glosslist) = glosstoken
        except ValueError:
            print glosstoken
        self.selectlist = selectlist
        self.vertical = vertical
        self.mbutton = None
        self.parent = parent
        self.children = []
        self.parserstage = self.stage
        self.index = index

        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)

        if self.vertical:
            self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            self.sizer = wx.BoxSizer(wx.VERTICAL)


        #FIXME: should I keep token string and use it here in spite of glosslist's first form?
        if len(self.glosslist) > 1:
            self.gloss = Gloss(self.form, set([]), '', ())
            self.statecode = 2
        elif ''.join(self.glosslist[0].ps) in ['', None, '<?>'] and self.glosslist[0].gloss in ['', None, '<?>']:
            self.gloss = Gloss(self.glosslist[0].form, set([]), '', ())
            self.statecode = -1
        else:
            self.gloss = self.glosslist[0]
            self.statecode = 1
        
        self.UpdateState(self.statecode, self.gloss)

        self.sizerflags = (wx.EXPAND | wx.TOP | wx.BOTTOM, 4)
        self.sizer.Add(self.mbutton, 0, *self.sizerflags)

        self.AddButtons(self.glosslist)

        if selectlist:
            for gloss in selectlist:
                for button in self.children:
                    if button.gloss == gloss:
                        button.main.SetValue(True)
                        button.OnToggled(None)
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
        self.SetSizer(self.sizer)
        self.Layout()
        self.parent.Layout()
        self.parent.Refresh()

    def OnEdition(self, gloss):
        self.gloss = gloss
        self.glosslist = [gloss] + [button.gloss for button in self.children]
        selectedbuttons = [button.gloss for button in self.children if button.selected]
        if selectedbuttons:
            self.selectlist = [gloss] + selectedbuttons
        else:
            self.selectlist = [gloss]
        self.statecode = 0
        self.UpdateState(self.statecode, self.gloss)

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
                self.statecode = 0
                self.gloss = self.selectlist[0]
                self.mbutton.gloss = self.selectlist[0]
                self.stage = 'gdisamb.0'
            elif len(self.selectlist) == 0:
                self.statecode = 2
                self.gloss = Gloss(self.children[0].gloss.form, set([]), '', ())
                self.stage = self.parserstage
            else:
                print "Bug: Negative selection!", selected
        else:
            self.gloss = gloss
            self.glosslist = [gloss]
            self.selectlist = [gloss]
            self.statecode = 0
            self.stage = 'gdisamb.-1'
        self.UpdateState(self.statecode, self.gloss)

    def GetToken(self):
        return (self.toktype, (self.form, self.stage, self.glosslist))

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
        if self.index == 0:
            joinbw.Enable(False)
        elif not tokens[self.index-1][0] == 'w':
            joinbw.Enable(False)
        if self.index == len(tokens)-1:
            joinfw.Enable(False)
        elif not tokens[self.index+1][0] == 'w':
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
        newform = firsttoken[1][0] + nexttoken[1][0]
        newtoken = ('w', (newform, '-1', [Gloss(newform, set([]),'',())]))
        sentstate[1][first] = []
        del sentstate[1][second]
        sentstate[2][first] = newtoken
        del sentstate[2][second]
        sentpanel.ShowSent(sentstate, sentpanel.snum)

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
                    sentstate[2].insert(self.index+shift, ('w', (token, '-1', [Gloss(token, set([]), '', ())])))
                    shift = shift+1
                sentpanel.ShowSent(sentstate, sentpanel.snum)

    def OnChangeTokenType(self, evt):
        pass

class NonglossToken(wx.Panel):
    def __init__(self, parent, index, nonglosstoken, selectlist, vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.toktype, self.toktext = nonglosstoken
        self.selectlist = selectlist
        self.index = index
        if self.toktype in ['c', 'Tag']:
            text = self.toktext
        else:
            text = '<...>'
        widget = wx.StaticText(self, -1, text)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(widget,0)
        self.SetSizer(sizer)

    def GetToken(self):
        return (self.toktype, self.toktext)


class SentenceAnnotation(wx.ScrolledWindow):
    def __init__(self, parent, sentglosses, sentselect, vertical=False, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.vertical = vertical
        self.children = []

        if vertical:
            self.Sizer = wx.BoxSizer(wx.VERTICAL)
        else:
            self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        for (index, (glosstoken,selectlist)) in enumerate(zip(sentglosses,sentselect)):
            if glosstoken[0] == 'w':
                abox = GlossSelector(self, index, glosstoken, selectlist, vertical=self.vertical)
            else:
                abox = NonglossToken(self, index, glosstoken, selectlist)
            self.children.append(abox)
            self.Sizer.Add(abox)
        self.SetSizer(self.Sizer)
        self.Layout()


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
        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.savedstate = None

    def ShowSent(self, senttuple, snum):
        self.senttext, self.selectlist, self.tokenlist, self.sentindex = senttuple
        self.snum = snum
        #FIXME: segfaults here
        for c in self.Sizer.GetChildren():
            if c.IsWindow():
                w = c.GetWindow()
            elif c.IsSizer():
                w = c.GetSizer()
            self.Sizer.Detach(w)
            w.Show(False)
        #self.Sizer = wx.BoxSizer(wx.VERTICAL)
        sentfont = wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)

        self.sentsource = wx.StaticText(self, -1, self.senttext)
        self.sentsource.SetFont(sentfont)
        self.sentsource.SetForegroundColour('Navy')
        prevbutton = wx.Button(self, -1, '<')
        prevbutton.Bind(wx.EVT_BUTTON, self.PrevSentence)
        nextbutton = wx.Button(self, -1, '>')
        nextbutton.Bind(wx.EVT_BUTTON, self.NextSentence)
        prevbutton.SetFont(sentfont)
        nextbutton.SetFont(sentfont)
        savebutton = wx.Button(self, -1, 'Save results')
        savebutton.Bind(wx.EVT_BUTTON, self.OnSaveResults)
        sentwidth = self.GetClientSize().GetWidth()-savebutton.GetClientSize().GetWidth()-(nextbutton.GetClientSize().GetWidth()*2)-5
        self.sentsource.Wrap(sentwidth)
        sentsizer = wx.BoxSizer(wx.HORIZONTAL)
        sentsizer.Add(prevbutton, 0)
        sentsizer.Add(self.sentsource, 1,wx.EXPAND)
        sentsizer.Add(nextbutton, 0)
        sentsizer.Add(savebutton, 0, wx.ALIGN_RIGHT)
        self.Sizer.Add(sentsizer, 0, wx.EXPAND)
        self.annotlist = SentenceAnnotation(self, self.tokenlist, self.selectlist, vertical=self.vertical)
        self.Sizer.Add(self.annotlist, 1, wx.EXPAND)
        #self.SetSizer(self.Sizer)
        self.Layout()

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
        tokenlist = []
        self.selectlist = []
        for selector in self.annotlist.children:
            if selector.selectlist:
                self.GetTopLevelParent().processor.dirty = True
            self.selectlist.append(selector.selectlist)
            tokenlist.append(selector.GetToken())
        self.GetTopLevelParent().processor.glosses[self.snum] = tuple([self.senttext, self.selectlist, tokenlist, self.sentindex])

    def SaveClicked(self, event):
        self.OnSaveResults(event)
        self.GetTopLevelParent().OnSave(event)

class MainFrame(wx.Frame):
    'Main frame'
    def __init__(self, parent, *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)

        filemenu= wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN,"O&pen"," Open text file")
        self.Bind(wx.EVT_MENU, self.OnOpen, menuOpen)
        menuSave = filemenu.Append(wx.ID_SAVE,"S&ave"," Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSave, menuSave)
        menuSaveAs = filemenu.Append(wx.ID_SAVEAS,"S&ave as"," Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSaveAs, menuSaveAs)
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
        menuBar.Append(settingsmenu,"&Settings") 
        self.SetMenuBar(menuBar)  

        self.dirname = os.curdir
        self.infile = None
        self.outfile = None
        self.dictfile = 'localdict.txt'
        self.processor = FileParser()
        self.filepanel = FilePanel(self)
        self.sentpanel = SentPanel(self)

        #FIXME: loading localdict right on start, should give user possibility to choose
        if os.path.exists(self.dictfile):
            self.localdict = formats.DictReader(self.dictfile).udict
        else:
            self.localdict = trie({})

        self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.Sizer.Add(self.sentpanel, 2, wx.EXPAND)
        self.Sizer.Add(self.filepanel, 1, wx.EXPAND)
        self.SetSizer(self.Sizer)
        self.Show()

    def OnVerticalMode(self,e):
        vertical = not self.sentpanel.vertical
        snum = self.sentpanel.snum
        self.sentpanel.OnSaveResults(e)
        oldsentpanel = self.sentpanel
        self.sentpanel = SentPanel(self,vertical=vertical)
        self.Sizer.Detach(oldsentpanel)
        oldsentpanel.Show(False)
        self.Refresh()
        self.Sizer.Insert(0, self.sentpanel,2,wx.EXPAND)
        self.Layout()
        self.sentpanel.ShowSent(self.processor.glosses[snum], snum)
        self.Layout()

    def OnUndoTokens(self,e):
        savedstate = self.sentpanel.savedstate
        if savedstate:
            snum = self.sentpanel.snum
            self.processor.glosses[snum] = savedstate
            self.sentpanel.ShowSent(savedstate, snum)
            savedstate = None
        else:
            print "No undo information"

    def OnExit(self,e):
        if self.processor.dirty:
            self.OnSave(e)
        self.Close(True)

    def NoFileError(self,e):
        dlg = wx.MessageDialog(self, 'Error: no file opened!', 'No file opened', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            self.processor.read_file(self.infile)
            self.filepanel.ShowFile(t[0] for t in self.processor.glosses)
            self.sentpanel.ShowSent(self.processor.glosses[0], 0)
            self.Layout()
        dlg.Destroy()

    def SaveFiles(self,e):
        if self.localdict:
            formats.DictWriter(self.localdict, self.dictfile, lang='default', name='localdict',ver='0').write()
        self.processor.write(self.outfile)


    def OnSave(self,e):
        if not self.infile:
            self.NoFileError(e)
        else:
            if not self.outfile:
                self.OnSaveAs(e)
            else:
                self.SaveFiles(e)

    def OnSaveAs(self,e):
        if not self.infile:
            self.NoFileError(e)
        else:
            xfilename = os.path.splitext(self.infile)[0]
            if not xfilename.endswith('.disamb'):
                xfilename = '.'.join([xfilename, 'disamb'])

            dlg = wx.FileDialog(self, "Choose a file", os.path.dirname(self.infile), xfilename, "*.html", wx.SAVE)
            if dlg.ShowModal() == wx.ID_OK:
                self.outfile = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
                if not os.path.splitext(self.outfile)[1] == '.html' :
                    self.outfile = ''.join([self.outfile, os.path.extsep, 'html'])
                    self.SaveFiles(e)
            dlg.Destroy()


if __name__ == '__main__':
    app = wx.App()
    frame = MainFrame(None, title="Bamana disambiguation interface (GUI)")
    frame.Show()
    app.MainLoop()

