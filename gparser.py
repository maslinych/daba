#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Graphical interface for the morphological parser
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
import os
import parser
from contextlib import contextmanager

class FilePanel(wx.Panel):
    'Text fileview panel'
    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.control = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        Sizer = wx.BoxSizer(wx.VERTICAL)
        Sizer.Add(self.control, 1, wx.EXPAND)
        self.SetSizer(Sizer)
        self.SetAutoLayout(1)

class ResourcePanel(wx.Panel):
    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)

        Sizer = wx.BoxSizer(wx.VERTICAL)
        dictbox = wx.StaticBox(self, -1, "Available Dictionaries")
        self.dsizer = wx.StaticBoxSizer(dictbox, wx.VERTICAL)
        Sizer.Add(self.dsizer, 1, wx.EXPAND)
         
        grambox = wx.StaticBox(self, -1, "Available Grammar")
        self.gsizer = wx.StaticBoxSizer(grambox, wx.VERTICAL)
        Sizer.Add(self.gsizer, 1, wx.EXPAND)

        self.SetSizer(Sizer)
        self.SetAutoLayout(1)
        

class MainFrame(wx.Frame):
    'Main frame'
    def __init__(self, parent, *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)

        # setup Processor
        dl = parser.DictLoader()
        gr = parser.GrammarLoader()
        self.processor = parser.Processor(dl.dictionary, gr.grammar)

        self.dirname = os.curdir
        self.infile = None
        self.outfile = None
        
        self.filepanel = FilePanel(self)
        self.resourcepanel = ResourcePanel(self)

        dictlist = wx.StaticText(self.resourcepanel, -1, '\n'.join(dl.dictlist))
        self.resourcepanel.dsizer.Add(dictlist, 0, wx.TOP|wx.LEFT, 10)

        gramlist = wx.StaticText(self.resourcepanel, -1, '\n'.join(gr.gramlist))
        self.resourcepanel.gsizer.Add(gramlist, 0, wx.TOP|wx.LEFT, 10)

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
        

        Sizer = wx.BoxSizer(wx.HORIZONTAL)
        Sizer.Add(self.filepanel, 2, wx.EXPAND)
        Sizer.Add(self.resourcepanel, 1, wx.EXPAND)
        self.SetSizer(Sizer)
        self.SetAutoLayout(1)
        self.Fit()


    def OnParse(self,e):
        @contextmanager
        def wait_for_parser():
            yield self.processor.parse()

        dlg = wx.MessageDialog(self, 'Please wait: parsing in progress', 'Pleade wait', wx.OK)
        dlg.ShowModal()

        with wait_for_parser():
            dlg.Destroy()
            self.FinishedParsing(e)

    def NoFileError(self,e):
        dlg = wx.MessageDialog(self, 'Error: no file opened!', 'No file opened', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def FinishedParsing(self,e):
        dlg = wx.MessageDialog(self, 'Parsing finished successfully', 'Parsing finished successfully', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnExit(self,e):
        self.Close(True)

    def OnOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            self.processor.read_file(self.infile)
            self.filepanel.control.SetValue('\n\n'.join(self.processor.txt))
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
    frame = MainFrame(None, title="Bamana morphological parser (GUI)")
    frame.Show()
    app.MainLoop()

