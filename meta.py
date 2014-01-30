#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Corpus metadata metaeditor
#
# Copyright (C) 2010—2012  Kirill Maslinsky <kirill@altlinux.org>
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

import wx
import wx.lib.intctrl
import wx.lib.masked
import os
import re
import xml.etree.cElementTree as e
from xml.parsers.expat import ExpatError
from collections import namedtuple
import tempfile
import shutil


class MetaConfig(object):
    def __init__(self, conffile=None):
        tree = e.ElementTree()
        config = tree.parse(conffile)
        field = namedtuple('Field', 'id type name default')
        def parse_value(elem):
            if 'list' in elem.attrib['type']:
                elem.attrib['default'] = [i.attrib['name'] for i in elem.findall('list/item')]
            else:
                elem.attrib['default'] = None
            return elem.attrib

        #FIXME: make it a list
        self.data = {}
        for sec in config.findall('section'):
            self.data[sec.attrib['id']] = (sec.attrib, 
                    [field(**parse_value(f)) for f in sec.findall('field')])

        self.widgets = {
                'text': (wx.TextCtrl, None, None),
                'long_text': (wx.TextCtrl, None, {'style': wx.TE_MULTILINE}),
                'int': (wx.lib.intctrl.IntCtrl, None, None),
                'closed_list': (wx.Choice, 'choices', None),
                'open_list': (wx.ComboBox, 'choices', None),
                'checklist': (wx.CheckListBox, 'choices', None),
                'date': (wx.GenericDatePickerCtrl, None, None),
                'datetext': (wx.lib.masked.Ctrl, None, {'autoformat': 'EUDATEDDMMYYYY.'}),
                }

        operate = namedtuple('Operate', 'get set')
        def parse_date(str):
            d = wx.DateTime()
            d.ParseDate(str)
            return d
        self.wvalues = {
                'text': operate(wx.TextCtrl.GetValue, wx.TextCtrl.SetValue),
                'long_text': operate(wx.TextCtrl.GetValue, wx.TextCtrl.SetValue),
                'int': operate(wx.lib.intctrl.IntCtrl.GetValue, 
                    lambda w,t: wx.lib.intctrl.IntCtrl.SetValue(w,int(t))),
                'closed_list': operate(wx.Choice.GetStringSelection, wx.Choice.SetStringSelection),
                'open_list': operate(wx.ComboBox.GetValue, wx.ComboBox.SetValue),
                'checklist': operate(lambda t: ';'.join(wx.CheckListBox.GetCheckedStrings(t)), 
                    lambda w,t: wx.CheckListBox.SetCheckedStrings(w, t.split(';'))),
                'date': operate(lambda t: wx.GenericDatePickerCtrl.GetValue(t).FormatDate(),
                    lambda w,t: wx.GenericDatePickerCtrl.SetValue(w, parse_date(t))),
                'datetext': operate(wx.lib.masked.TextCtrl.GetValue,
                    wx.lib.masked.BaseMaskedTextCtrl.SetValue),
                }

    def makeLabel(self, parent, tuple):
        return wx.StaticText(parent, label=tuple.name)

    def makeWidget(self, parent, tuple):
        widget, default, kwargs = self.widgets[tuple.type]
        if not kwargs:
            kwargs = {}
        if default:
            kwargs[default] = tuple.default
        return widget(parent, **kwargs)


class DataPanel(wx.ScrolledWindow):
    def __init__(self, parent, config=None, section=None, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.widgetlist = dict()
        self.config = config
        self.section = section
        gridSizer = wx.FlexGridSizer(rows=1,cols=2,hgap=10,vgap=10)

        expandOption = dict(flag=wx.EXPAND)
        noOptions = dict()
        for wdata in self.config.data[self.section][1]:
            # prepare widget data for future use
            name = wdata.id
            widget = self.config.makeWidget(self,wdata) 
            wtype = wdata.type
            self.widgetlist[name] = (widget,wtype)
            # position widget on the plane
            gridSizer.Add(self.config.makeLabel(self,wdata), **noOptions)
            gridSizer.Add(widget, **expandOption)
        self.SetSizer(gridSizer)
        self.Layout()


class MetaPanel(wx.Panel):
    'Panel holding metadata'
    def __init__(self, parent, config=None, section=None, multiple=False, sep="|", *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.config = config
        self.section = section
        self.multiple = multiple
        self.sep = sep
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.panels = []
        self.title = self.config.data[self.section][0]['name']

        if multiple:
            buttons = wx.BoxSizer(wx.HORIZONTAL)
            addbutton = wx.Button(self, -1, "Rajouter un " + self.title)
            addbutton.Bind(wx.EVT_BUTTON, self.addPanel)
            delbutton = wx.Button(self, -1, "Effacer un " + self.title)
            delbutton.Bind(wx.EVT_BUTTON, self.delPanel)
            buttons.Add(addbutton, 0, 0, 0)
            buttons.Add(delbutton, 0, 0, 0)
            self.sizer.Add(buttons)
            self.panelbook = wx.Notebook(self)
            self.addPanel()
            self.sizer.Add(self.panelbook, 1, wx.EXPAND, 0)
        else:
            self.addPanel()
        self.sizer.Fit(self)
        self.Layout()

    def addPanel(self, evt=None):
        if self.multiple:
            panel = DataPanel(self.panelbook, config=self.config, section=self.section)
            self.panelbook.AddPage(panel, self.title + " " + str(len(self.panels)+1))
        else:
            panel = DataPanel(self, config=self.config, section=self.section)
            self.sizer.Add(panel, 1, wx.EXPAND, 0)
        self.panels.append(panel)
        self.Layout()

    def delPanel(self, evt=None):
        current = self.panelbook.GetSelection()
        if self.multiple:
            self.panelbook.DeletePage(current)
            del self.panels[current]
            self.Layout()
        else:
            pass

    def setValue(self, field, value):
        if self.multiple:
            vlist = value.split(self.sep)
            while len(vlist) > len(self.panels):
                self.addPanel()
        else:
            vlist = [value]
        for val,panel in zip(vlist, self.panels):
            widget, wtype = panel.widgetlist[field]
            self.config.wvalues[wtype].set(widget, val)
        
    def collectValues(self):
        result = {}
        for panel in self.panels:
            for name, (widget,wtype) in panel.widgetlist.iteritems():
                fieldname = ':'.join([self.section,name])
                value = self.config.wvalues[wtype].get(widget)
                try:
                    result[fieldname] = self.sep.join([result[fieldname], unicode(value)]) 
                except (KeyError):
                    result[fieldname] = unicode(value)
        return result



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

class MainFrame(wx.Frame):
    """Main frame."""
    def __init__(self, parent, config, encoding='utf-8', *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)

        self.init_values()
        self.config = config
        self.metapanels = {}
        self.encoding = encoding

        filemenu= wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN,"O&pen"," Open text file")
        self.Bind(wx.EVT_MENU, self.OnOpen, menuOpen)
        menuSave = filemenu.Append(wx.ID_SAVE,"S&ave"," Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSave, menuSave)
        menuSaveAs = filemenu.Append(wx.ID_SAVEAS,"S&ave as"," Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSaveAs, menuSaveAs)
        menuClose = filemenu.Append(wx.ID_CLOSE, "C&lose","Close current file")
        self.Bind(wx.EVT_MENU, self.OnClose, menuClose)
        menuExit = filemenu.Append(wx.ID_EXIT,"E&xit"," Terminate the program")
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File") # Adding the "filemenu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.

        splitter = wx.SplitterWindow(self)
        self.filepanel = FilePanel(splitter)
        self.notebook = wx.Notebook(splitter)
        self.draw_metapanels()

        splitter.SplitVertically(self.filepanel, self.notebook)
        splitter.SetMinimumPaneSize(20)

        self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.Sizer.Add(splitter, 1, wx.EXPAND)
        #Sizer.Add(self.filepanel, 1, wx.EXPAND)
        #Sizer.Add(notebook, 1, wx.EXPAND)
        self.SetSizer(self.Sizer)
        self.Layout()

    def init_values(self):
        self.filename = None
        self.dirname = os.curdir
        self.metadata = {}
        self.txt = ''

    def draw_metapanels(self):
        for sec in self.config.data:
            if 'multiple' in self.config.data[sec][0]:
                multiple = True
            else:
                multiple = False
            metapanel = MetaPanel(self.notebook, config=self.config, section=sec, multiple=multiple)
            self.metapanels[sec] = metapanel
            self.notebook.AddPage(metapanel, self.config.data[sec][0]['name'])

    def parse_file(self,ifile):
        tree = e.ElementTree()
        if os.path.splitext(ifile.name)[1] in ['.html', '.xhtml', '.xml']:
            try:
                self.xml = tree.parse(ifile)
            except ExpatError:
                #FIXME: show error message
                self.filename = None
            if self.xml:
                self.update_interface()
                self.txt = u'\n\n'.join([p.text or '' for p in self.xml.findall('body/p')])
        elif os.path.splitext(ifile.name)[1] in ['.txt']:
            self.txt = ifile.read().decode(self.encoding)
            html = e.Element('html')
            head = e.SubElement(html, 'head')
            e.SubElement(head, 'meta', {'http-equiv': "Content-Type", 'content': "text/html; charset={0}".format(self.encoding)})
            body = e.SubElement(html, 'body')
            for p in re.split(r'(\r?\n)+\r?\n', self.txt):
                if p:
                    para = e.SubElement(body, 'p')
                    para.text = p
            self.xml = html
        else:
            self.filename = None

    def update_interface(self):
        head = self.xml.find('head')
        for meta in self.xml.findall('head/meta'):
            try:
                name = meta.attrib['name']
                content = meta.attrib['content']
                self.metadata[name] = content
                try:
                    sec, field = name.split(':')
                except ValueError:
                    print "Unknown meta field:", name, content
                    break
                self.metapanels[sec].setValue(field, content)
            except KeyError:
                pass

    def update_metadata(self):
        # collect all metadata given
        for mp in self.metapanels.itervalues():
            self.metadata.update(mp.collectValues())
        head = self.xml.find('head')
        metaheaders = {}
        
        for m in self.xml.findall('head/meta'):
            try:
                name = m.attrib['name']
                if name in metaheaders:
                    print "Duplicate metadata values:", name
                else:
                    metaheaders[name] = m
            except KeyError:
                pass

        for k,v in self.metadata.iteritems():
            if v:
                if k in metaheaders:
                    metaheaders[k].attrib['content'] = unicode(v)
                else:
                    e.SubElement(head, 'meta', {'name':k, 'content': unicode(v)})
            else:
                if k in metaheaders:
                    head.remove(metaheaders[k])

    def write_xmldata(self):
        self.update_metadata()
        tempout = tempfile.NamedTemporaryFile(delete=False)
        try: 
            e.ElementTree(self.xml).write(tempout)
        except TypeError:
            #FIXME: show proper error message
            print "Serialization error"
            print e.dump(e.ElementTree(self.xml))
        tempout.close()    
        with open(tempout.name, 'r') as infile:
            try:
                with open(os.path.join(self.dirname, self.filename),'wb') as outfile:
                    shutil.copyfileobj(infile, outfile)
            except IOError:
                #FIXME: show proper error message
                print "Error writing file!"
        os.unlink(tempout.name)

    def NoFileError(self,e):
        dlg = wx.MessageDialog(self, 'Error: no file opened!', 'No file opened', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnExit(self,e):
        self.Close(True)

    def OnOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = dlg.GetPath()
            self.filename = os.path.basename(self.infile)
            self.dirname = os.path.dirname(self.infile)
            with open(os.path.join(self.dirname, self.filename), 'r') as f:
                self.parse_file(f)
                self.filepanel.control.SetValue(self.txt)
        dlg.Destroy()

    def OnSave(self,e):
        if not self.filename:
            self.NoFileError(e)
        if os.path.splitext(self.filename)[1] in ['.html', '.xhtml', '.xml']:
            self.write_xmldata()
        else:
            self.OnSaveAs(e)

    def OnSaveAs(self,e):
        if not self.filename:
            self.NoFileError(e)
        else:
            xfilename = os.path.splitext(self.filename)[0]

            dlg = wx.FileDialog(self, "Choose a file", self.dirname, xfilename, "*.html", wx.SAVE)
            if dlg.ShowModal() == wx.ID_OK:
                self.outfile = dlg.GetPath()
                self.filename = os.path.basename(self.outfile)
                self.dirname = os.path.dirname(self.outfile)
                if not os.path.splitext(self.filename)[1] == '.html':
                    self.filename = ''.join([self.filename, os.path.extsep, 'html'])
                with open(os.path.join(self.dirname, self.filename), 'w') as xhtml:
                    self.write_xmldata()
            dlg.Destroy()

    def OnClose(self,e):
        self.OnSave(e)
        self.init_values()
        self.notebook.DeleteAllPages()
        self.draw_metapanels()


if __name__ == '__main__':
    confname = 'meta.xml'
    metaconfig = MetaConfig(confname)
    app = wx.App()
    frame = MainFrame(None, config=metaconfig, title="Bamana corpus metaeditor")
    frame.Show()
    app.MainLoop()

