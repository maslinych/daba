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
from ntgloss import Gloss
import xml.etree.cElementTree as e
from disambiguator import parse_sent

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
        ]

makeGlossString = lambda gloss: u'{0} ({1})\n{2}'.format(gloss.form, '/'.join(gloss.ps), gloss.gloss)

class FileParser(object):
    def __init__(self):
        self.xml = None
        self.glosses = []
        self.txt = ''

    def read_file(self, filename):
        self.xml = e.parse(filename)
        self.txt = []
        for p in self.xml.findall('body/p'):
            for sent in p.findall('span'):
                if sent.attrib['class'] == 'sent':
                    stup = parse_sent(sent)
                    self.glosses.append(stup)
                    self.txt.append(stup[0])


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
            self.parent.parent.sentpanel.ShowSent(self.parent.parent.processor.glosses[self.num])
            self.parent.parent.Layout()

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
        addb.Bind(wx.EVT_BUTTON, self.OnAddMorpheme)

        vbox_top.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0)
        self.SetSizer(vbox_top)

    def GetGloss(self):
        form = self.form.GetValue()
        ps = set(self.ps.GetCheckedStrings())
        gloss = self.gloss.GetValue()
        morphemes = tuple(self.morphemes)
        return Gloss(form, ps, gloss, morphemes)

    def OnAddMorpheme(self, event):
        if PSLIST[0] is not 'mrph':
            PSLIST.insert(0, 'mrph')
        dlg = GlossInputDialog(self, -1, "Add morpheme", pos=map(lambda x: x+20, self.GetPositionTuple()) )
        if (dlg.ShowModal() == wx.ID_OK):
            self.morphemes.append(dlg.GetGloss())


class GlossEditButton(wx.Panel):
    def __init__(self, parent, form, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.button = wx.Button(self, -1, form, style=wx.NO_BORDER)
        sizer.Add(self.button,0)
        self.button.SetSizer(sizer)
        self.button.Bind(wx.EVT_BUTTON, self.OnShowPopup)
        self.parent = parent #FIXME: find a better way to reference GlossSelector
        self.statecolours = {
                1: 'Black',
                2: 'Navy',
                3: 'Blue',
                -1: 'DarkRed',
                0: 'DarkGreen'
                }
        
    def OnShowPopup(self, event):
        dlg = GlossInputDialog(self, -1, 'Insert gloss manually')
        if (dlg.ShowModal() == wx.ID_OK):
            self.parent.OnSelection(dlg.GetGloss())
        dlg.Destroy()

    def OnStateChange(self, statecode, glossstring):
        self.button.SetLabel(glossstring)
        self.button.Layout()
        try:
            self.button.SetForegroundColour(self.statecolours[statecode])
        except KeyError:
            #FIXME: proper error message
            print 'Unknown state code:', statecode



class GlossSelector(wx.Panel):
    def __init__(self, parent, glosslist, vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.glosslist = glosslist
        self.selectlist = []
        self.vertical = vertical
        self.mbutton = None
        self.children = []

        if self.vertical:
            sizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            sizer = wx.BoxSizer(wx.VERTICAL)

        #FIXME: should I keep token string and use it here in spite of glosslist's first form?
        if len(glosslist) > 1:
            self.glossstring = glosslist[0].form
            self.statecode = 2
        elif ''.join(glosslist[0].ps) in ['', None, '<?>'] and glosslist[0].gloss in ['', None, '<?>']:
            self.glossstring = glosslist[0].form
            self.statecode = -1
        else:
            self.glossstring = makeGlossString(glosslist[0])
            self.statecode = 1
        
        self.UpdateState(self.statecode, self.glossstring)

        sizerflags = (wx.EXPAND | wx.TOP | wx.BOTTOM, 4)
        sizer.Add(self.mbutton, 0, *sizerflags)
        if len(glosslist) > 1:
            for gloss in self.glosslist:
                gbutton = GlossButton(self, gloss)
                self.children.append(gbutton)
                sizer.Add(gbutton, 0, *sizerflags)

        self.SetSizer(sizer)

    def UpdateState(self, statecode, glossstring):
        if not self.mbutton:
            self.mbutton = GlossEditButton(self, self.glossstring)
        self.mbutton.OnStateChange(self.statecode, self.glossstring)
        self.Layout()

    def OnSelection(self, gloss):
        if self.children:
            self.selectlist = [button.gloss for button in self.children if button.selected]
            print self.selectlist
            if len(self.selectlist) > 1:
                self.statecode = 3
                self.glosstring = makeGlossString(self.selectlist[0])
            elif len(self.selectlist) == 1:
                self.statecode = 0
                self.glossstring = makeGlossString(self.selectlist[0])
            elif len(self.selectlist) == 0:
                self.statecode = 2
                self.glossstrng = self.children[0].gloss.form
            else:
                print "Bug: Negative selection!", selected
        else:
            self.glossstring = makeGlossString(gloss)
            self.selectlist = [gloss]
            self.statecode = 0
        self.UpdateState(self.statecode, self.glossstring)


class SentenceAnnotation(wx.ScrolledWindow):
    def __init__(self, parent, senttuple, vertical=True, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.vertical = vertical

        if vertical:
            self.Sizer = wx.BoxSizer(wx.VERTICAL)
        else:
            self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        for glosslist in senttuple[1]:
            abox = GlossSelector(self, glosslist, vertical=self.vertical)
            self.Sizer.Add(abox)
        self.Sizer.Fit(self)
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
    def __init__(self, parent, senttuple=('', ()), vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.senttuple = senttuple
        self.vertical = vertical
        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        #self.SetSizer(self.Sizer)

    def ShowSent(self, sent):
        self.senttuple = sent
        self.Sizer.Clear(deleteWindows=True)
        self.Sizer = wx.BoxSizer(wx.VERTICAL)

        self.sentsource = wx.StaticText(self, -1, self.senttuple[0])
        self.sentsource.SetFont(wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.sentsource.SetForegroundColour('Navy')
        savebutton = wx.Button(self, -1, 'Save results')
        self.sentsource.Wrap(self.GetClientSize().GetWidth()-savebutton.GetClientSize().GetWidth()-5)
        sentsizer = wx.BoxSizer(wx.HORIZONTAL)
        sentsizer.Add(self.sentsource, 1,wx.EXPAND)
        sentsizer.Add(savebutton, 0, wx.ALIGN_RIGHT)
        self.Sizer.Add(sentsizer, 0, wx.EXPAND)
        self.annotlist = SentenceAnnotation(self, self.senttuple, vertical=self.vertical)
        self.Sizer.Add(self.annotlist, 1, wx.EXPAND)
        self.Sizer.Fit(self)
        self.SetSizer(self.Sizer)
        self.Layout()

        #self.Sizer.Fit(self)
        #self.SetSizer(self.Sizer)
        #self.parent.OnUpdate()


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
        
        self.dirname = os.curdir
        self.processor = FileParser()
        self.filepanel = FilePanel(self)
        self.sentpanel = SentPanel(self)

        self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.Sizer.Add(self.sentpanel, 2, wx.EXPAND)
        self.Sizer.Add(self.filepanel, 1, wx.EXPAND)
        self.SetSizer(self.Sizer)
        self.Show()

    def OnUpdate(self):
        self.Layout()

    def OnExit(self,e):
        self.Close(True)

    def OnOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            self.processor.read_file(self.infile)
            self.filepanel.ShowFile(self.processor.txt)
            self.sentpanel.ShowSent(self.processor.glosses[0])
            self.Layout()
        dlg.Destroy()

    def OnSave(self,e):
        if not self.infile:
            self.NoFileError(e)
        if not self.outfile:
            self.OnSaveAs(e)
        else:
            self.OnParse(e)
            self.processor.write(self.outfile)

    def OnSaveAs(self,e):
        if not self.infile:
            self.NoFileError(e)
        else:
            xfilename = '.'.join([os.path.splitext(self.infile)[0], 'parsed'])

            dlg = wx.FileDialog(self, "Choose a file", os.path.dirname(self.infile), xfilename, "*.html", wx.SAVE)
            if dlg.ShowModal() == wx.ID_OK:
                self.outfile = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
                if not os.path.splitext(self.outfile)[1] == '.html' :
                    self.outfile = ''.join([self.outfile, os.path.extsep, 'html'])
                    self.OnParse(e)
                    self.processor.write(self.outfile)
            dlg.Destroy()


if __name__ == '__main__':
    app = wx.App()
    frame = MainFrame(None, title="Bamana disambiguation interface (GUI)")
    frame.Show()
    app.MainLoop()

