#!/usr/bin/env python3
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
from contextlib import contextmanager

import daba.mparser
# import daba.formats   # already loaded in mparser!
from daba.plugins import OrthographyConverter

def get_outdir(fname):
    dirname = os.path.dirname(fname)
    basename = os.path.basename(fname)
    if os.path.basename(dirname) == 'txt':
        dirname = os.path.join(os.path.dirname(dirname), 'pars')
        if not os.path.exists(dirname):
            try:
                os.mkdir(dirname)
            except OSError:
                print("Could not create output directory, please do it manually")
    return dirname

def get_outfile(fname):
    basename = os.path.basename(fname)
    # <<<< +JJM
    parsfile='.'.join([os.path.splitext(basename)[0], 'pars.html'])  
    if os.path.exists(parsfile): 
        print("get_outfile / EXISTE DÉJÀ / ALREADY EXISTS: ",parsfile)
        os.remove(parsfile)
        print("  fichier précédent SUPPRIMÉ / previous file DELETED/removed")
        # NO SELF HERE self.statusbar.SetStatusText(" fichier pars précédent supprimé:"+parsfile)
    # >>>> +JJM
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
        print("dic :",dic)
        hbox.Add(wx.StaticText(self, -1, dic.description),0)
        rbutton = wx.Button(self, b_id, "Remove")
        self.Bind(wx.EVT_BUTTON, parent.OnRemove, rbutton)
        hbox.Add(rbutton,0)
        self.SetSizer(hbox)
        self.Layout()

import wx.lib.scrolledpanel as scrolled
class DictionaryLister(scrolled.ScrolledPanel):
    def __init__(self, parent, dictloader, *args, **kwargs):
        super(DictionaryLister, self).__init__(parent,
                                      style = wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        self.SetupScrolling()
        #wx.Panel.__init__(self, parent, *args, **kwargs)
        self.buttons = {}
        self.children = {}
        self.parent = parent
        self.dictloader = dictloader
        dictbox = wx.StaticBox(self, -1, "Available Dictionaries")
        dictbox.SetBackgroundColour((236, 211, 211, 255))   # was (60, 25, 25, 25)
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
        grambox.SetBackgroundColour((236, 211, 211, 255)) # was (80, 40, 40, 30)
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

class ConverterLister(scrolled.ScrolledPanel):
    def __init__(self, parent, *args, **kwargs):
        super(ConverterLister, self).__init__(parent,
                                style = wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        self.SetupScrolling()
        #wx.Panel.__init__(self, parent, *args, **kwargs)
        #FIXME: make default plugins configurable from config file
        self.selection = ('apostrophe',)
        daba.mparser.load_plugins()
        converterbox = wx.StaticBox(self, -1, "Available Orthographic Converters")
        converterbox.SetBackgroundColour((236, 211, 211, 255)) # was (70, 30, 30, 30)
        self.csizer = wx.StaticBoxSizer(converterbox, wx.VERTICAL)
        print("OrthographyConverter.converters",OrthographyConverter.converters)
        self.converterlist = wx.CheckListBox(self, wx.ID_ANY, choices=OrthographyConverter.converters)
        self.converterlist.SetBackgroundColour((236, 211, 211, 255)) # was (60, 25, 25, 25)
        self.converterlist.SetCheckedStrings(self.selection)
        self.Bind(wx.EVT_CHECKLISTBOX, self.OnSelection, self.converterlist)
        self.csizer.Add(self.converterlist, 0, wx.TOP|wx.LEFT, 10)
        self.SetSizer(self.csizer)
        self.Layout()

    def OnSelection(self, evt):
        self.selection = self.converterlist.GetCheckedStrings()


class TokenizerLister(wx.Panel):
    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.selection = 'default'
        self.tkz = daba.mparser.Tokenizer()
        self.tokenizers = self.tkz.methods
        tokenizerbox = wx.StaticBox(self, wx.ID_ANY, "Available Tokenizers")
        tokenizerbox.SetBackgroundColour((236, 211, 211, 255)) # was (60, 25, 25, 30)
        self.tsizer = wx.StaticBoxSizer(tokenizerbox, wx.VERTICAL)
        self.tokenizerlist = wx.RadioBox(self, wx.ID_ANY, choices=self.tokenizers)
        self.tokenizerlist.SetSelection(self.tokenizerlist.FindString(self.selection))
        self.Bind(wx.EVT_RADIOBOX, self.OnSelection, self.tokenizerlist)
        self.tsizer.Add(self.tokenizerlist, 0, wx.TOP|wx.LEFT, 10)
        self.SetSizer(self.tsizer)
        self.Layout()

    def OnSelection(self, evt):
        self.selection = self.tokenizerlist.GetString(self.tokenizerlist.GetSelection())
        self.tkz.use_method(self.selection)


class ResourcePanel(wx.Panel):
    def __init__(self, parent, dictloader, grammarloader, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)

        Sizer = wx.BoxSizer(wx.VERTICAL)
        dictlist = DictionaryLister(self, dictloader)
        Sizer.Add(dictlist, 1, wx.EXPAND)
         
        gramlist = GrammarLister(self, grammarloader)
        Sizer.Add(gramlist, 0, wx.EXPAND)

        self.toklist = TokenizerLister(self)
        Sizer.Add(self.toklist, 0, wx.EXPAND)

        self.convlist = ConverterLister(self)
        Sizer.Add(self.convlist, 1, wx.EXPAND)

        self.SetSizer(Sizer)
        self.SetAutoLayout(True)


class MainFrame(wx.Frame):
    'Main frame'
    def __init__(self, parent, *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)
        self.InitValues()

        wx.Config.Set(wx.Config("gparser", style=wx.CONFIG_USE_LOCAL_FILE))
        self.config = wx.Config.Get(False)
        self.config.SetRecordDefaults()

        # setup Resources
        self.dirname = os.curdir
        self.dl = daba.mparser.DictLoader()
        self.gr = daba.mparser.GrammarLoader()
        self.resourcepanel = ResourcePanel(self, self.dl, self.gr)
        self.filepanel = FilePanel(self)

        self.statusbar = self.CreateStatusBar(1)  # JJM
        self.statusbar.SetStatusText('Bienvenue dans le parseur (gparser) !')

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

        x=self.config.ReadInt("MainFrame/pos/x",30)     # JJM : recover previous layout
        y=self.config.ReadInt("MainFrame/pos/y",30)
        w=self.config.ReadInt("MainFrame/size/w",512)
        h=self.config.ReadInt("MainFrame/size/h",756)
        print("config ReadInt x,y,w,h",x,y,w,h)
        self.SetPosition(wx.Point(x,y))
        self.SetSize(wx.Rect(x,y,w,h))

    def InitValues(self):
        self.infile = None
        self.outfile = None
        self.io = daba.formats.FileWrapper()
        self.parsed = False

    def OnParse(self,e):
        @contextmanager
        def wait_for_parser():
            print("OnParse / self.resourcepanel.toklist.tkz.methods:",self.resourcepanel.toklist.tkz.methods) # JJM
            #for n, tok in enumerate(self.resourcepanel.toklist.tkz):   # JJM
            #    print("OnParse / self.resourcepanel.toklist / n, tok :",n,tok)
            print("OnParse / self.resourcepanel.convlist.selection:",self.resourcepanel.convlist.selection) # JJM
            self.processor = daba.mparser.Processor(self.dl, self.gr,
                                               tokenizer=self.resourcepanel.toklist.tkz,
                                               converters=self.resourcepanel.convlist.selection)
            yield self.processor.parse(self.io.para)

        dlg = wx.MessageDialog(self, 'Please wait: parsing in progress', 'Please wait', wx.OK)
        self.statusbar.SetStatusText("parsing en cours... (mparser) ")
        dlg.ShowModal()

        if not self.parsed:
            with wait_for_parser():
                self.parsed = True
                dlg.Destroy()
                self.FinishedParsing(e)
                myparsfile=self.outfile.replace(self.dirname,"")
                self.statusbar.SetStatusText("parsing terminé / finished :"+myparsfile)
        else:
            #FIXME: proper error message or better avoid this case!
            print("File already parsed!")
            myparsfile=self.outfile.replace(self.dirname,"")
            self.statusbar.SetStatusText("votre fichier est déjà parsé / already parsed :"+myparsfile+" -> PLEASE file/close")

    def NoFileError(self,e):
        dlg = wx.MessageDialog(self, 'Error: no file opened!', 'No file opened', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def FinishedParsing(self,e):
        dlg = wx.MessageDialog(self, 'Parsing finished successfully', 'Parsing finished successfully', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnExit(self,e):
        #   JJM save window position and size
        x,y=self.Position 
        w,h=self.Size
        self.config.WriteInt("MainFrame/pos/x",x)
        self.config.WriteInt("MainFrame/pos/y",y)
        self.config.WriteInt("MainFrame/size/w",w)
        self.config.WriteInt("MainFrame/size/h",h)
        self.config.Flush()  # permanently writes
        print("config WriteInt x,y,w,h",x,y,w,h)

        self.Close(True)

    def OnOpen(self, e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "gparser files (txt/html)|*.html;*.txt", wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
        # caution: it would be nice to filter out localdict.txt and pars.html, dis.html files
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = dlg.GetPath()
            if self.infile.endswith(".pars.html") or self.infile.endswith(".dis.html") or self.infile.endswith(".repl.html"):
                fileerror = wx.MessageDialog(self, "incompatible file type", self.infile, wx.OK)
                fileerror.ShowModal()
                fileerror.Destroy()
            else:
                self.dirname = os.path.dirname(self.infile)

                try:
                    self.io.read(self.infile)
                    self.SetTitle("gparser: "+self.infile)
                    self.parsed = False
                    self.filepanel.control.SetValue('\n\n'.join(self.io.para))
                    #print("self.io.metadata['text:script']:",self.io.metadata['text:script']) # JJM
                    try: 
                        myscript=self.io.metadata['text:script']
                    except KeyError:
                        myscript='***NO SCRIPT***'
                        dlg = wx.MessageDialog(self, 'Please choose from the Available orthographic converters (or none if "Nouvel orthographe malien", only "apostrophe")', 'The file has no meta information for text:script',  wx.OK)
                        dlg.ShowModal()
                    print("OnOpen / metas / script:",myscript)
                    myscriptcode=''
                    mytokcode=''
                    if   myscript=='Nouvel orthographe malien':
                        mytokcode="bamana"
                    elif myscript=='Ancien orthographe malien': 
                        myscriptcode='bamlatinold'
                        mytokcode="bamana"
                    elif myscript=='N&#8217;Ko' or myscript=="N’Ko": 
                        myscriptcode='nko'
                        mytokcode="nko"
                    if myscriptcode=='': 
                        myselection=('apostrophe',)
                    else:
                        myselection=('apostrophe',myscriptcode)
                    if mytokcode=='':
                        mytokmethods=['default']
                    else:
                        mytokmethods=[mytokcode]
                    print("OnOpen / myselection:",myselection)
                    print("OnOpen / mytokmethods:",mytokmethods)
                    self.resourcepanel.convlist.selection=myselection
                    self.resourcepanel.toklist.tkz.methods=mytokmethods
                    # update interface accordingly
                    try:
                        self.resourcepanel.toklist.tokenizerlist.SetSelection(self.resourcepanel.toklist.tokenizerlist.FindString(mytokcode))
                    except:
                        print("mytokcode:",mytokcode," radio box index:",self.resourcepanel.toklist.tokenizerlist.FindString(mytokcode))
                    self.resourcepanel.convlist.converterlist.SetCheckedStrings(myselection)
                    
                    
                    myfile=self.infile.replace(self.dirname,"")
                    self.statusbar.SetStatusText("fichier ouvert:"+myfile+"     text:script: "+myscript)
                except ValueError as e:
                    fileerror = wx.MessageDialog(self, "Unknown file type", "Unknown file type", wx.OK)
                    fileerror.ShowModal()
                    fileerror.Destroy()
        dlg.Destroy()

    def OnClose(self,e):
        #   JJM save window position and size
        x,y=self.Position 
        w,h=self.Size
        self.config.WriteInt("MainFrame/pos/x",x)
        self.config.WriteInt("MainFrame/pos/y",y)
        self.config.WriteInt("MainFrame/size/w",w)
        self.config.WriteInt("MainFrame/size/h",h)
        self.config.Flush()  # permanently writes
        print("config WriteInt x,y,w,h",x,y,w,h)

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

