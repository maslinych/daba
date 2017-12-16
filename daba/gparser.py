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
import mparser
import formats
from contextlib import contextmanager
from plugins import OrthographyConverter

def get_outdir(fname):
    dirname = os.path.dirname(fname)
    basename = os.path.basename(fname)
    if os.path.basename(dirname) == 'txt':
        dirname = os.path.join(os.path.dirname(dirname), 'pars')
        if not os.path.exists(dirname):
            try:
                os.mkdir(dirname)
            except OSError:
                print "Could not create output directory, please do it manually"
    return dirname

def get_outfile(fname):
    basename = os.path.basename(fname)
    return '.'.join([os.path.splitext(basename)[0], 'pars'])


class FilePanel(wx.Panel):
    'Text fileview panel'
    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.control = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        Sizer = wx.BoxSizer(wx.VERTICAL)
        Sizer.Add(self.control, 1, wx.EXPAND)
        self.SetSizer(Sizer)
        self.SetAutoLayout(True)

class DictionaryItem(wx.Panel):
    def __init__(self, parent, dic, b_id, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(wx.StaticText(self, -1, dic.description),0)
        rbutton = wx.Button(self, b_id, "Remove")
        self.Bind(wx.EVT_BUTTON, parent.OnRemove, rbutton)
        hbox.Add(rbutton,0)
        self.SetSizer(hbox)
        self.Layout()


class DictionaryLister(wx.Panel):
    def __init__(self, parent, dictloader, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.buttons = {}
        self.children = {}
        self.parent = parent
        self.dictloader = dictloader
        dictbox = wx.StaticBox(self, -1, "Available Dictionaries")
        self.dsizer = wx.StaticBoxSizer(dictbox, wx.VERTICAL)
        b_id = 0
        for dic in self.dictloader.dictionary.dictlist:
            b_id = b_id + 10
            self.buttons[b_id] = dic.hash
            d_item = DictionaryItem(self, dic, b_id)
            self.children[dic.hash] = d_item
            self.dsizer.Add(d_item,0, wx.TOP|wx.LEFT,10)
        abutton = wx.Button(self, -1, "Add dictionary")
        self.Bind(wx.EVT_BUTTON, self.OnAdd, abutton)
        self.dsizer.Add(abutton,0,wx.TOP|wx.LEFT,10)
        self.SetSizer(self.dsizer)
        self.Layout()

    def OnRemove(self, evt):
        dictid = self.buttons[evt.GetId()]
        self.dictloader.remove(dictid)
        c_id = self.children[dictid]
        self.dsizer.Detach(c_id)
        c_id.Show(False)
        del self.buttons[evt.GetId()]
        del self.children[dictid]
        self.dsizer.Layout()
        
        
    def OnAdd(self, evt):
        dlg = wx.FileDialog(self, message="Select dictionary file", wildcard="Toolbox dict (*.txt)|*.txt", style=wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            dictfile = dlg.GetPath()
            dictid = self.dictloader.addfile(dictfile)
            if not dictid in self.children:
                try:
                    b_id = max(self.buttons.keys())+10
                except (ValueError):
                    b_id = 10
                self.buttons[b_id] = dictid
                d_item = DictionaryItem(self, self.dictloader.dictionary.get_dict(dictid), b_id)
                self.children[dictid] = d_item
                self.dsizer.Insert(0, d_item, 0, wx.TOP|wx.LEFT,10)
                self.dsizer.Layout()
                self.Refresh()


class GrammarLister(wx.Panel):
    def __init__(self, parent, grammarloader, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)

        self.grammarloader = grammarloader
        grambox = wx.StaticBox(self, -1, "Available Grammar")
        self.gsizer = wx.StaticBoxSizer(grambox, wx.VERTICAL)
        self.gramlist = wx.StaticText(self, -1, '\n'.join(self.grammarloader.gramlist))
        self.gsizer.Add(self.gramlist, 0, wx.TOP|wx.LEFT, 10)
        gbutton = wx.Button(self, -1, "(Re)Load grammar")
        self.gsizer.Add(gbutton, 0, wx.TOP|wx.LEFT, 10)
        self.Bind(wx.EVT_BUTTON, self.OnLoad, gbutton)
        self.SetSizer(self.gsizer)
        self.Layout()

    def OnLoad(self, evt):
        dlg = wx.FileDialog(self, message="Select grammar file", wildcard="Mparser grammar (*.txt)|*.txt", style=wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            gramfile = dlg.GetPath()
            self.grammarloader.load(gramfile)
            oldname = self.gramlist
            oldname.Show(False)
            self.gramlist = wx.StaticText(self, -1, '\n'.join(self.grammarloader.gramlist))
            self.gsizer.Replace(oldname, self.gramlist)
            self.gramlist.Show(True)
            self.Layout()

class ConverterLister(wx.Panel):
    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        #FIXME: make default plugins configurable from config file
        self.selection = ('apostrophe',)
        mparser.load_plugins()
        self.converters = OrthographyConverter.get_plugins().keys()
        converterbox = wx.StaticBox(self, -1, "Available Orthographic Converters")
        self.csizer = wx.StaticBoxSizer(converterbox, wx.VERTICAL)
        self.converterlist = wx.CheckListBox(self, wx.ID_ANY, choices=self.converters)
        self.converterlist.SetCheckedStrings(self.selection)
        self.Bind(wx.EVT_CHECKLISTBOX, self.OnSelection, self.converterlist)
        self.csizer.Add(self.converterlist, 0, wx.TOP|wx.LEFT, 10)
        self.SetSizer(self.csizer)
        self.Layout()

    def OnSelection(self, evt):
        self.selection = self.converterlist.GetCheckedStrings()

class ResourcePanel(wx.Panel):
    def __init__(self, parent, dictloader, grammarloader, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)

        Sizer = wx.BoxSizer(wx.VERTICAL)
        dictlist = DictionaryLister(self, dictloader)
        Sizer.Add(dictlist, 1, wx.EXPAND)
         
        gramlist = GrammarLister(self, grammarloader)
        Sizer.Add(gramlist, 0, wx.EXPAND)

        self.convlist = ConverterLister(self)
        Sizer.Add(self.convlist, 1, wx.EXPAND)

        self.SetSizer(Sizer)
        self.SetAutoLayout(True)
        
class MainFrame(wx.Frame):
    'Main frame'
    def __init__(self, parent, *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)
        self.InitValues()
        # setup Resources
        self.dirname = os.curdir
        self.dl = mparser.DictLoader()
        self.gr = mparser.GrammarLoader()
        self.resourcepanel = ResourcePanel(self, self.dl, self.gr)
        self.filepanel = FilePanel(self)

        filemenu= wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN,"O&pen"," Open text file")
        self.Bind(wx.EVT_MENU, self.OnOpen, menuOpen)
        menuSave = filemenu.Append(wx.ID_SAVE,"S&ave"," Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSave, menuSave)
        menuSaveAs = filemenu.Append(wx.ID_SAVEAS,"S&ave as"," Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSaveAs, menuSaveAs)
        menuClose = filemenu.Append(wx.ID_CLOSE,"C&lose","Close current file")
        self.Bind(wx.EVT_MENU,self.OnClose, menuClose)
        menuExit = filemenu.Append(wx.ID_EXIT,"E&xit"," Terminate the program")
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File") # Adding the "filemenu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.
        
        Sizer = wx.BoxSizer(wx.HORIZONTAL)
        Sizer.Add(self.filepanel, 2, wx.EXPAND)
        Sizer.Add(self.resourcepanel, 1, wx.EXPAND)
        self.SetSizer(Sizer)
        self.SetAutoLayout(True)
        self.Fit()

    def InitValues(self):
        self.infile = None
        self.outfile = None
        self.io = formats.FileWrapper()
        self.parsed = False

    def OnParse(self,e):
        @contextmanager
        def wait_for_parser():
            self.processor = mparser.Processor(self.dl, self.gr, converters=self.resourcepanel.convlist.selection)
            yield self.processor.parse(self.io.para)

        dlg = wx.MessageDialog(self, 'Please wait: parsing in progress', 'Please wait', wx.OK)
        dlg.ShowModal()

        if not self.parsed:
            with wait_for_parser():
                self.parsed = True
                dlg.Destroy()
                self.FinishedParsing(e)
        else:
            #FIXME: proper error message or better avoid this case!
            print "File already parsed!"

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

    def OnOpen(self, e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = dlg.GetPath()
            self.dirname = os.path.dirname(self.infile)
            try:
                self.io.read(self.infile)
                self.parsed = False
                self.filepanel.control.SetValue('\n\n'.join(self.io.para))
            except ValueError as e:
                fileerror = wx.MessageDialog(self, "Unknown file type", "Unknown file type", wx.OK)
                fileerror.ShowModal()
                fileerror.Destroy()
        dlg.Destroy()

    def OnClose(self,e):
        self.filepanel.control.Clear()
        self.InitValues()

    def OnSave(self,e):
        if not self.infile:
            self.NoFileError(e)
        if not self.outfile:
            self.OnSaveAs(e)
        else:
            self.OnParse(e)
            self.io.write(self.outfile, result=self.processor.parsed, parsed=True)

    def OnSaveAs(self,e):
        if not self.infile:
            self.NoFileError(e)
        else:
            dlg = wx.FileDialog(self, "Choose a file", get_outdir(self.infile), get_outfile(self.infile), "*.html", wx.FD_SAVE)
            if dlg.ShowModal() == wx.ID_OK:
                self.outfile = dlg.GetPath()
                if not os.path.splitext(self.outfile)[1] == '.html' :
                    self.outfile = ''.join([self.outfile, os.path.extsep, 'html'])
                    self.OnParse(e)
                    self.io.write(self.outfile, result=self.processor.parsed, parsed=True)
            dlg.Destroy()


def main():
    app = wx.App()
    frame = MainFrame(None, title="Bamana morphological parser (GUI)")
    frame.Show()
    app.MainLoop()

if __name__ == '__main__':
    main()

