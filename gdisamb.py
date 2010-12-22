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




class SentText(wx.StaticText):
    def __init__(self, parent, id, num=None, *args, **kwargs):
        wx.StaticText.__init__(self, parent, *args, **kwargs)
        self.num = num
        self.parent = parent

    def onMouseEvent(self, event):
        if event.Moving():
            self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        elif event.LeftDown():
            self.parent.parent.sentpanel.showSent(self.parent.parent.processor.glosses[self.num])

        event.Skip()

class FilePanel(wx.ScrolledWindow):
    'Text fileview panel'
    def __init__(self, parent, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.parent = parent

    def showFile(self, sentlist):
        Sizer = wx.BoxSizer(wx.VERTICAL)
        sentSizer = wx.BoxSizer(wx.VERTICAL)
        for n, sent in enumerate(sentlist):
            st = SentText(self, -1, num=n, style=wx.ST_NO_AUTORESIZE)
            st.SetLabel(sent)
            st.Wrap(self.GetClientSize().GetWidth()-20)
            st.Bind(wx.EVT_LEFT_DOWN, st.onMouseEvent)
            Sizer.Add(st, 1, wx.EXPAND)
        panel = sentSizer
        Sizer.Add(panel, 1, wx.EXPAND)

        self.SetSizer(Sizer)
        self.SetScrollbars(20, 20, 0, 0)
        self.Sizer.Fit(self)
        self.Show()

class GlossButton(wx.ToggleButton):
    def __init__(self, parent, *args, **kwargs):
        wx.ToggleButton.__init__(self, parent, *args, **kwargs)
        self.selected = False
        self.children = []

    def onToggled(self, event):
        self.selected = not self.selected
        if self.selected:
            self.SetForegroundColour("Blue")
        else:
            self.SetForegroundColour("Black")
        for child in self.children:
            child.onToggled(event)


class SentPanel(wx.Panel):
    'Manual disambiguation panel'
    def __init__(self, parent, vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.vertical = vertical
        self.Sizer = wx.BoxSizer(wx.VERTICAL)

    def showSent(self, sent):
        def makeGlossItem(parent, text):
            text = wx.StaticText(parent, -1, text)
            text.SetFont(wx.Font(18, None, None, None))
            return text

        def makeGlossBox(parent, gloss, child=False):
            box = wx.BoxSizer(wx.VERTICAL)
            #form = makeGlossItem(parent, gloss.form)
            #ps = makeGlossItem(parent, '/'.join(gloss.ps))
            #ge = makeGlossItem(parent, gloss.gloss)
            #box.Add(form, 0, wx.SUNKEN_BORDER)
            #box.Add(ps, 0, wx.SUNKEN_BORDER)
            #box.Add(ge, 0, wx.SUNKEN_BORDER)
            tb = GlossButton(self, -1, u'{0} ({1})\n{2}'.format(gloss.form, '/'.join(gloss.ps), gloss.gloss))
            tb.Bind(wx.EVT_TOGGLEBUTTON, tb.onToggled)
            box.Add(tb, 0)
            #if child:
            #    parent.children.append(tb)
            if gloss.morphemes:
                morphemes = wx.BoxSizer(wx.HORIZONTAL)
                for morph in gloss.morphemes:
                    m = makeGlossBox(parent, morph, child=True)
                    morphemes.Add(m, 0)
                box.Add(morphemes, 0)
            return box

        def makeGlossSizer(parent, glosslist):
            if self.vertical:
                box = wx.BoxSizer(wx.HORIZONTAL)
            else:
                box = wx.BoxSizer(wx.VERTICAL)
            for gloss in glosslist:
                gbox = makeGlossBox(parent, gloss)
                box.Add(gbox, 0, wx.SUNKEN_BORDER)
                #box.Add(wx.StaticLine(self, wx.HORIZONTAL), 0, wx.EXPAND)
            return box

        def makeAnnotSizer(parent, annotlist):
            if self.vertical:
                box = wx.BoxSizer(wx.VERTICAL)
            else:
                box = wx.BoxSizer(wx.HORIZONTAL)

            for glosslist in annotlist:
                abox = makeGlossSizer(parent, glosslist)
                box.Add(abox)
            return box

        def makeSent(parent, text):
            return wx.StaticText(parent, -1, text)

        self.Sizer.Clear(deleteWindows=True)
        self.sent = wx.BoxSizer(wx.VERTICAL)
        self.annot = wx.BoxSizer(wx.VERTICAL)

        self.sent.Add(makeSent(self, sent[0]), 0,wx.EXPAND)
        self.Sizer.Add(self.sent, 0)
        self.annot.Add(makeAnnotSizer(self, sent[1],), wx.EXPAND)
        self.Sizer.Add(self.annot, 0)
        self.SetSizer(self.Sizer)
        self.SetAutoLayout(1)
        self.Sizer.Fit(self)
        self.Show()

    def showCurrent(self, nth):
        pass


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

        Sizer = wx.BoxSizer(wx.HORIZONTAL)
        Sizer.Add(self.sentpanel, 2, wx.EXPAND)
        Sizer.Add(self.filepanel, 1, wx.EXPAND)
        self.SetSizer(Sizer)
        #self.SetAutoLayout(1)
        self.Fit()



    def OnExit(self,e):
        self.Close(True)

    def OnOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            self.processor.read_file(self.infile)
            #self.filepanel.control.SetValue('\n\n'.join(self.processor.txt))
            self.filepanel.showFile(self.processor.txt)
            self.sentpanel.showSent(self.processor.glosses[0])
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

