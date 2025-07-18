#!/usr/bin/env python3
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
import wx.adv
import wx.lib.intctrl
import wx.lib.masked
import os
import re
import xml.etree.cElementTree as e
from xml.parsers.expat import ExpatError
from collections import namedtuple, defaultdict
import tempfile
import shutil
import csv
import uuid
import daba.formats


class MetaData(object):
    def __init__(self, metadict=None):
        self.namesep = u':'
        self.valuesep = u'|'
        self._data = defaultdict(lambda: defaultdict(tuple))
        if metadict:
            self.fromPlain(metadict)

    def fromPlain(self, metadict):
        for mkey, mvalue in metadict.items():
            try:
                section, name = mkey.split(self.namesep)
            except (ValueError):
                print(u"Malformed meta field: {} {}".format(name, mvalue))
            values = mvalue.split(self.valuesep)
            self._data[section][name] = values

    def toPlain(self):
        return dict(
                (self.namesep.join([section, name]), self.valuesep.join(values)) 
                for section, d in self._data.items() for name, values in d.items()
                )

    def getSection(self, section):
        fnames, fvalues = zip(*[(k,v) for k,v in self._data[section].items()])
        return list(map(lambda vs: zip(fnames, vs), zip(*fvalues)))

    def setSection(self, section, secdata):
        for name, values in  map(lambda x: (x[0][0], list(zip(*x))[1]), zip(*secdata)):
            self._data[section][name] = values

    def sections(self):
        for secname in self._data.keys():
            if secname != "_auto":
                yield (secname, self.getSection(secname))


FieldConfig = namedtuple('FieldConfig', 'id type name default readonly')
FieldConfig.__new__.__defaults__ = (None, None, None, None, None)


class MetaConfig(object):
    def __init__(self, conffile=None):
        self.confdir = os.path.dirname(conffile)
        tree = e.ElementTree()
        config = tree.parse(conffile)

        def parse_field_xml(elem):
            if 'list' in elem.attrib['type']:
                elem.attrib['default'] = [i.attrib['name'] for i in elem.findall('list/item')]
            else:
                elem.attrib['default'] = None
            return elem.attrib

        self._data = {}
        for sec in config.findall('section'):
            if 'save' in sec.attrib:
                if not os.path.isabs(sec.attrib['save']):
                    sec.attrib['dbfile'] = os.path.join(self.confdir, sec.attrib['save'])
            self._data[sec.attrib['id']] = (sec.attrib, 
                    [FieldConfig(**parse_field_xml(f)) for f in sec.findall('field')])

    def getSectionConfig(self, section):
        return self._data[section][1]

    def getSectionTitle(self, section):
        return self._data[section][0]['name']

    def getSectionFieldnames(self, section):
        return [':'.join([section, fconfig.id]) for fconfig in self._data[section][1]]

    def getSectionAttributes(self, section):
        return self._data[section][0]

    def sections(self):
        return self._data.keys()


class GUIBuilder(object):
    def __init__(self):
        self.widgets = {
                'text': (wx.TextCtrl, None, None),
                'long_text': (wx.TextCtrl, None, {'style': wx.TE_MULTILINE, 'size':(300,100)}),
                'int': (wx.lib.intctrl.IntCtrl, None, None),
                'closed_list': (wx.Choice, 'choices', None),
                'open_list': (wx.ComboBox, 'choices', None),
                'checklist': (wx.CheckListBox, 'choices', None),
                'date': (wx.adv.DatePickerCtrl, None, {'style': wx.adv.DP_DROPDOWN|wx.adv.DP_SHOWCENTURY}),
                'datetext': (wx.lib.masked.Ctrl, None, {'autoformat': 'EUDATEDDMMYYYY.'}),
                }
        operate = namedtuple('Operate', 'get set')
        def parse_date(str):
            d = wx.DateTime()
            d.ParseDate(str)
            return d
        self.wvalues = {
                'text': operate(wx.TextCtrl.GetValue, 
                    lambda w,t: wx.TextCtrl.SetValue(w, str(t))),
                'long_text': operate(wx.TextCtrl.GetValue, 
                    lambda w,t: wx.TextCtrl.SetValue(w, str(t))),
                'int': operate(wx.lib.intctrl.IntCtrl.GetValue, 
                    lambda w,t: wx.lib.intctrl.IntCtrl.SetValue(w,int(t) if t else 0)),
                'closed_list': operate(wx.Choice.GetStringSelection, 
                    lambda w,t: wx.Choice.SetStringSelection(w, str(t) if t else u'inconnu')),
                'open_list': operate(wx.ComboBox.GetValue, 
                    lambda w,t: wx.ComboBox.SetValue(w, str(t))),
                'checklist': operate(lambda t: ';'.join(wx.CheckListBox.GetCheckedStrings(t)), 
                    lambda w,t: wx.CheckListBox.SetCheckedStrings(w, t.split(';'))),
                'date': operate(lambda t: wx.adv.DatePickerCtrl.GetValue(t).Format("%d.%m.%Y"),
                    lambda w,t: wx.adv.DatePickerCtrl.SetValue(w, parse_date(t))),
                'datetext': operate(wx.lib.masked.TextCtrl.GetValue,
                    lambda w,t: wx.lib.masked.BaseMaskedTextCtrl.SetValue(w, str(t))),
                }

    def makeLabel(self, parent, field):
        return wx.StaticText(parent, label=field.name)

    def makeWidget(self, parent, field):
        widget, default, kwargs = self.widgets[field.type]
        if not kwargs:
            kwargs = {}
        if default:
            kwargs[default] = field.default
        result = widget(parent, **kwargs)
        if field.readonly:
            result.Enable(False)
        return result

    def getWidgetValue(self, wtype, widget):
        return str(self.wvalues[wtype].get(widget))

    def setWidgetValue(self, wtype, widget, value):
        try:
            self.wvalues[wtype].set(widget, value)
        except (AssertionError):
            if value:
                print(u"Incorrect value '{0}' for field '{1}' will be ignored".format(widget, value))
                return False
        return True

    
class DataPanel(wx.ScrolledWindow):
    def __init__(self, parent, config=None, section=None, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.widgetlist = dict()
        self.config = config
        self.section = section
        self.builder = GUIBuilder() # FIXME make one instance at the top level
        gridSizer = wx.FlexGridSizer(cols=2, hgap=10, vgap=10)
        gridSizer.AddGrowableCol(1, 1)
        expandOption = dict(proportion=1, flag=wx.EXPAND)
        noOptions = dict(proportion=1)
        for wdata in self.config.getSectionConfig(self.section):
            # prepare widget data for future use
            name = wdata.id
            widget = self.builder.makeWidget(self, wdata)
            wtype = wdata.type
            self.widgetlist[name] = (widget, wtype)
            # position widget on the plane
            gridSizer.Add(self.builder.makeLabel(self, wdata), **noOptions)
            gridSizer.Add(widget, **expandOption)
        self.SetSizer(gridSizer)
        self.Layout()

    def setPanelData(self, secdata):
        for name, value in secdata:
            self.setFieldValue(name, value)

    def setFieldValue(self, name, value):
            widget, wtype = self.widgetlist[name]
            try:
                self.builder.setWidgetValue(wtype, widget, value)
            except (ValueError, TypeError):
                print("Problem with setting value", u'{1}, {2}:{3}'.format(wtype, name, value))

    def getPanelData(self):
        return [(name, self.getFieldValue(name)) for name in self.widgetlist.keys()]

    def getFieldValue(self, name):
        widget, wtype = self.widgetlist[name]
        return self.builder.getWidgetValue(wtype, widget)


class MetaDB(object):
    'Storage for reusable metadata values'
    def __init__(self, dbfile, secname, fieldnames, keyfield=None, idcolumn="uuid", namesep=":"):
        self._map = {}
        self._strmap = {}
        self.dbfile = dbfile
        self.secname = secname
        self.namesep = namesep
        self.fieldnames = fieldnames
        self.idcolumn = idcolumn
        self.keyfield = keyfield
        if os.path.exists(self.dbfile):
            with open(dbfile, 'r', encoding='utf-8') as csvfile:
                dbreader = csv.DictReader(csvfile, restval='')
                self.csvnames = dbreader.fieldnames
                for row in dbreader:
                    row = self._decode_row(row)
                    key = row[self.idcolumn]
                    self._map[key] = row
                    self._strmap[self._make_keystring(row)] = key
        else:
            self.csvnames = self.fieldnames

    def __contains__(self, key):
        return key in self._map

    def __getitem__(self, key):
        return self._map[key]

    def _strip_secname(self, mkey):
        prefix = self.secname + self.namesep
        if mkey.startswith(prefix):
            return mkey[len(prefix):]
        return mkey

    def _decode_row(self, row):   
        try:
            utf = dict((self._strip_secname(k),v) for k,v in row.items())
        except:
            print("-row : ",row)   # added JJM 24/12/2024
            sys.exit("***decode_row error***")

        if self.idcolumn not in utf.keys():
            key = self._add_uuid(utf)
        return utf

    def _add_uuid(self, mdict):
        key = str(uuid.uuid4())
        mdict[self.idcolumn] = key
        return key

    def _remove_uuid(self, mdict):
        return dict((k,v) for k,v in mdict.items() if k != self.idcolumn)

    def _add_secname(self, key):
        return self.namesep.join([self.secname, key])
    
    def _encode_row(self, row):
        utf = {}
        for k,v in row.items():
            utf[self._add_secname(k)] = v
        return utf

    def _normalize_row(self, row):
        for k,v in row.items():
            if row[k] in [0, "0", 'inconnu']:
                row[k] = ""
        return row

    def _row_as_string(self, row):
        try:
            return u' '.join([row[self._strip_secname(field)] for field in self.csvnames if self._strip_secname(field) != self.idcolumn])
        except (KeyError, TypeError):
            print(self.csvnames, row)
    
    def _make_keystring(self, mdict):
        return self._row_as_string(self._normalize_row(mdict))

    def is_not_trivial(self, mdict):
        return any(self._normalize_row(mdict).values())

    def has_keyfield(self, mdict):
        return self.keyfield in mdict

    def is_known_by_key(self, mdict):
        if self.idcolumn in mdict:
            return mdict[self.idcolumn] in self._map
        else:
            return False

    def _match_content(self, mdict, dbentry):
        return self._normalize_row(mdict) == self._remove_uuid(dbentry)

    def content_matches(self, mdict):
        return any([self._match_content(mdict, dbentry) for dbentry in self._map.values()])

    def append(self, mdict):
        key = self._add_uuid(mdict)
        dbentry = self._normalize_row(mdict)
        self._map[key] = dbentry
        self._strmap[self._make_keystring(mdict)] = key
        # print("mdict? : ",mdict) # JJM 27/12/2024
        # mdict? :  {'name': 'Fournier, Georges', 'spelling': '', 'sex': 'm', 'birth_year': '', 'dialect': 'France', 'native_lang': 'Français', 'addon': 'nyòninsan 1976 (avec Andrée Audibert)', 'uuid': 'cc1eced6-e66e-4e9a-9b6d-8b209c56b699'}
        if mdict['name']!='':    # JJM 27/12/2024 - do not update authors unnecessarily
            self.write()
        return dbentry

    def update(self, key, mdict):
        self._map[key] = self._normalize_row(mdict)
        if mdict['name']!='':    # JJM 27/12/2024 - do not update authors unnecessarily
            self.write()

    def getEntryByUUID(self, uuid):
        return self._map[uuid]

    def getEntryByKey(self, key):
        return self._map[self._strmap[key]]

    def getEntryUUID(self, mdict):
        if self.is_not_trivial(mdict) and self.has_keyfield(mdict):
            if self.is_known_by_key(mdict):
                return mdict[self.idcolumn]
            elif self.content_matches(mdict):
                for key, dbentry in self._map.items():
                    if self._match_content(mdict, dbentry):
                        return key
        else:
            return None

    def getList(self):
        return list(self._strmap.keys())

    def write(self):
        if self._map:
            with open(self.dbfile, 'w', encoding='utf-8') as csvfile:
                dbwriter = csv.DictWriter(csvfile, self.fieldnames, restval='')
                dbwriter.writeheader()
                rows = self._map.values()
                if self.keyfield:
                    try:
                        rows = sorted(rows, key=lambda d: d[self.keyfield])
                    except(KeyError):
                        pass
                for row in rows:
                    dbwriter.writerow(self._encode_row(row))


class MetaPanel(wx.Panel):
    'Panel holding metadata'
    def __init__(self, parent, config=None, section=None, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.config = config
        self.section = section
        self.secattrs = self.config.getSectionAttributes(self.section)
        self.multiple = 'multiple' in self.secattrs
        self.hasdbfile = 'dbfile' in self.secattrs 
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.panels = []
        self.title = self.config.getSectionTitle(self.section)
        self.db = None
    
        if self.hasdbfile:
            fieldnames = self.config.getSectionFieldnames(self.section)
            self.db = MetaDB(self.secattrs['dbfile'], self.section, fieldnames, keyfield=self.secattrs['keyfield'])
            searchbox = wx.BoxSizer(wx.HORIZONTAL)
            label = wx.StaticText(self, wx.ID_ANY, "Chercher dans la liste")
            choicelist = self.db.getList() or ['']
            self.selector = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
            self.selector.AutoComplete(choices=choicelist)
            self.selector.Bind(wx.EVT_TEXT_ENTER, self.onItemSelected)
            self.selector.Bind(wx.EVT_TEXT, self.onItemSelected)
            searchbox.Add(label)
            searchbox.Add(self.selector, 1, wx.EXPAND)
            self.sizer.Add(searchbox, 0, wx.EXPAND)

        if self.multiple:
            buttons = wx.BoxSizer(wx.HORIZONTAL)
            addbutton = wx.Button(self, -1, "Rajouter un " + self.title)
            addbutton.Bind(wx.EVT_BUTTON, self.addPanel)
            delbutton = wx.Button(self, -1, "Effacer un " + self.title)
            delbutton.Bind(wx.EVT_BUTTON, self.delPanel)
            buttons.Add(addbutton, 0, 0, 0)
            buttons.Add(delbutton, 0, 0, 0)
            self.sizer.Add(buttons)
            self.panelbook = wx.Notebook(self)
            self.sizer.Add(self.panelbook, 1, wx.EXPAND, 0)
        self.addPanel()
        self.Layout()

    def addPanel(self, evt=None):
        if self.multiple:
            panel = DataPanel(self.panelbook, config=self.config, section=self.section)
            self.panelbook.AddPage(panel, self.title + " " + str(len(self.panels)+1))
        else:
            panel = DataPanel(self, config=self.config, section=self.section)
            self.sizer.Add(panel, 1, wx.EXPAND, 0)
        panel.SetBackgroundColour((236, 211, 211, 255))  # was (96, 63, 63, 30) - (90, 50, 50, 30) (236, 211, 211, 255) (130, 80, 80, 30)
        self.panels.append(panel)
        self.Layout()

    def getCurrentPanelID(self):
        return self.panelbook.GetSelection()

    def getCurrentPanel(self):
        if len(self.panels) < 1:
            self.addPanel()
        return self.panels[self.getCurrentPanelID()]

    def delPanel(self, evt=None):
        current = self.getCurrentPanelID()
        if self.multiple:
            self.panelbook.DeletePage(current)
            del self.panels[current]
            self.Layout()
        else:
            #FIXME should the only panel be deleted anyway?
            pass

    def setSectionData(self, secdata):
        while len(secdata) > len(self.panels):
            self.addPanel()
        for panel, data in zip(self.panels, secdata):
            if self.db:
                # get updated data from db
                dbentrykey = self.db.getEntryUUID(dict(data))
                if dbentrykey:
                    data = self.db.getEntryByUUID(dbentrykey).items()
            panel.setPanelData(data)
            
    def setCurrentPanelData(self, secdata):
        self.getCurrentPanel().setPanelData(secdata)

    def getCurrentPanelData(self):
        return self.getCurrentPanel().getPanelData()

    def getSectionData(self):
        if self.db:
            self.saveDBEntries()
        return [panel.getPanelData() for panel in self.panels]

    def onItemSelected(self, values):
        if self.selector.IsModified():
            try:
                dbentry = self.db.getEntryByKey(self.selector.GetValue())
                self.setCurrentPanelData(dbentry.items())
            except KeyError:
                # print("KeyError :", self.selector.GetValue())  # JJM 04/01/2024
                pass

    def saveDBEntries(self):
        for panel in self.panels:
            mdict = dict(panel.getPanelData())
            dbentrykey = self.db.getEntryUUID(mdict)
            if dbentrykey:
                self.db.update(dbentrykey, mdict)
            else:
                dbentry = self.db.append(mdict)
                panel.setPanelData(dbentry.items())
                self.selector.AutoComplete(choices=self.db.getList())

class ResumePanel(wx.ScrolledWindow):
    def __init__(self, parent, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.parent = parent
        self.isMetaShown=False
        self.Sizer = wx.BoxSizer(wx.VERTICAL)

    def ShowMetas(self, metadata):

        if self.isMetaShown:
            self.Sizer.Clear(delete_windows=True)   # that's the key element missing : delete_windows=True
            self.Sizer.Remove(self.Sizer)   # probably does not do a thing...

        metas={}
        items=[]
        authors=False
        metatxt=""
        for item,y in metadata._data.items():
            #print("item,y",item,y)
            #metatxt+=item+" "+str(y)+"\n"
            for sitem,svalue in y.items():
                #print("sitem,svalue:",sitem,str(svalue))
                if item=="author":
                    if sitem=="name": sitem="_name" # force sorting as 1st
                elif item in ["source","text"] :
                    if sitem=="title": sitem="_title"
           
                thisvalue=', '.join(svalue)

                if item in items:
                    if item=="author" and authors:
                        authindex=0
                        for v in svalue:
                            authindex+=1
                            metas[item][authindex][sitem]=v
                    else:
                        metas[item][sitem]=thisvalue
                else: 
                    items.append(item)
                    if item=="author":
                        if len(svalue)>1:
                            authors=True
                            authindex=0
                            for v in svalue:
                                authindex+=1
                                if authindex==1: 
                                    metas[item]={authindex: {sitem:v}}
                                else :  metas[item][authindex]={sitem:v}
                        else:
                            metas[item]={sitem:thisvalue}
                    else:
                        metas[item]={sitem:thisvalue}
        
        #print("metas:",metas)
        # print sorted metas
        metatxt="Métadonnées\n"
        for x,y in sorted(metas.items()):
            metatxt+=x+"\n"
            for w,z in sorted(y.items()):
                if x=="author" and authors:
                    metatxt+="\t"+str(w)+"\n"
                    for wn,zn in sorted(z.items()):
                        metatxt+="\t\t"+wn.strip("_")+" :\t "+zn+"\n"
                else: 
                    metatxt+="\t"+w.strip("_")+" :\t "+str(z)+"\n"
        metatxt=metatxt.replace("\n","\n   ")
        metatxt=metatxt.replace(";"," ; ")

        self.st= wx.TextCtrl(self,style=wx.TE_MULTILINE|wx.TE_DONTWRAP)
        self.st.SetValue(metatxt)
        #font = wx.Font(12, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        #self.SetFont(font)
        self.metafont = self.GetFont()
        self.metafont.SetPointSize(self.metafont.GetPointSize() + 2)
        self.st.SetFont(self.metafont)
        self.Sizer.Add(self.st, 1, wx.EXPAND)        

        self.SetSizer(self.Sizer)
        self.Layout()
        self.isMetaShown=True


class MetaNotebook(wx.Notebook):
    """Notebook widget holding MetaPanels"""
    def __init__(self, parent, *args, **kwargs):
        wx.Notebook.__init__(self, parent, *args, **kwargs)
        Sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(Sizer)
        self.Layout()

class FilePanel(wx.Panel):
    'Text fileview panel'
    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.control = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        # self.control = wx.TextCtrl(self, style=wx.TE_MULTILINE)   # needs more work to enable text edits

        Sizer = wx.BoxSizer(wx.VERTICAL)
        Sizer.Add(self.control, 1, wx.EXPAND)
        self.SetSizer(Sizer)
        self.Layout()


class MainFrame(wx.Frame):
    """Main frame."""
    def __init__(self, parent, config=None, encoding='utf-8', *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)

        self.cleanup = True
        self.init_values()
        self.config = config
        self.dirname = os.curdir
        self.metapanels = {}
        self.encoding = encoding

        self.myconfig = wx.Config.Get()            # JJM 26/12/2024
        global confpath
        confpath = self.myconfig.Read("meta/confpath")
        print("_init_confpath=",confpath)
        if confpath!="": 
            self.config = MetaConfig(confpath)
            # self.SetTitle("["+confpath+"]")   # JJM 27/12/2024
        #wx.Config.Set(wx.Config("gparser", style=wx.CONFIG_USE_LOCAL_FILE))
        #self.config = wx.Config.Get(False)
        #self.config.SetRecordDefaults()

        x=self.myconfig.ReadInt("MainFrame/pos/x",30)     # JJM : recover previous layout
        y=self.myconfig.ReadInt("MainFrame/pos/y",30)
        w=self.myconfig.ReadInt("MainFrame/size/w",512)
        h=self.myconfig.ReadInt("MainFrame/size/h",256)
        #print("x,y,w,h",x,y,w,h)
        self.SetPosition(wx.Point(x,y))
        self.SetSize(wx.Rect(x,y,w,h))

        filemenu = wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN, "O&pen", " Open text file")
        self.Bind(wx.EVT_MENU, self.OnOpen, menuOpen)
        menuSave = filemenu.Append(wx.ID_SAVE, "S&ave", " Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSave, menuSave)
        menuSaveAs = filemenu.Append(wx.ID_SAVEAS, "S&ave as", " Save an xhtml file")
        self.Bind(wx.EVT_MENU, self.OnSaveAs, menuSaveAs)
        menuClose = filemenu.Append(wx.ID_CLOSE, "C&lose", "Close current file")
        self.Bind(wx.EVT_MENU, self.OnClose, menuClose)
        menuExit = filemenu.Append(wx.ID_EXIT, "E&xit"," Terminate the program")
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu, "&File") # Adding the "filemenu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.

        splitter = self.make_splitter()
        if self.config:
            self.draw_metapanels()

        configbutton = wx.FilePickerCtrl(self, -1, wildcard="*.xml", style=wx.FLP_USE_TEXTCTRL | wx.FLP_OPEN | wx.FLP_FILE_MUST_EXIST)
        configbutton.Bind(wx.EVT_FILEPICKER_CHANGED, self.OnConfigSelected)
        configbutton.SetTextCtrlProportion(2)
        configbutton.SetTextCtrlGrowable(True)
        if confpath!="":
            configbutton.SetPath(confpath)
        retainbutton = wx.ToggleButton(self, -1, 'Retain values for the next file')
        retainbutton.Bind(wx.EVT_TOGGLEBUTTON, self.OnRetainToggled)
        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.Sizer.Add(configbutton, 0, wx.EXPAND)
        self.Sizer.Add(retainbutton)
        self.Sizer.Add(splitter, 1, wx.EXPAND)
        self.SetSizer(self.Sizer)
        self.Layout()

    def make_splitter(self):
        splitter = wx.SplitterWindow(self, wx.ID_ANY, style=wx.SP_LIVE_UPDATE)
        splitter.SetMinimumPaneSize(100)
        self.filepanel = FilePanel(splitter)
        self.notebook = MetaNotebook(splitter)
        self.notebook.SetBackgroundColour((236, 211, 211, 255))  # was (96, 63, 63, 30) - (236, 211, 211, 255) (90, 50, 50, 30)
        splitter.SplitVertically(self.filepanel, self.notebook)
        return splitter
        
    def init_values(self):
        self.filename = None
        if self.cleanup:
            self.metadata = MetaData()
        self.txt = ''

    def draw_metapanels(self):
        for secname in self.config.sections():
            metapanel = MetaPanel(self.notebook, config=self.config, section=secname)
            # metapanel.Bind(wx.EVT_KILL_FOCUS, self.update_metadata)   # does not work, only Save fixes metadata for Résumé
            self.metapanels[secname] = metapanel
            self.notebook.AddPage(metapanel, self.config.getSectionTitle(secname))
        # add résumé 
        self.resumepanel = ResumePanel(self.notebook)
        # self.resumepanel.Bind(wx.EVT_SET_FOCUS, self.resumepanel.ShowMetas(self.metadata))
        self.notebook.AddPage(self.resumepanel, "[Résumé]")
        self.Layout()

    def clear_metapanels(self):
        self.metapanels = {}
        splitter = self.Sizer.GetChildren()[-1].GetWindow()
        splitter.Destroy()
        splitter = self.make_splitter()
        self.Sizer.Add(splitter, 1, wx.EXPAND)
        self.Layout()

    def parse_file(self, ifile):
        self.io = daba.formats.FileWrapper()
        self.io.read(ifile)
        self.metadata = MetaData(self.io.metadata)
        self.txt = u''.join([p for p in self.io.para if p is not None])

    def update_interface(self):
        for secname, secdata in self.metadata.sections():
            self.metapanels[secname].setSectionData(secdata)
        # update résumé
        self.resumepanel.ShowMetas(self.metadata)

    def update_metadata(self):
        # collect all metadata given
        for secname, mp in self.metapanels.items():
            self.metadata.setSection(secname, mp.getSectionData())
        # update résumé
        self.resumepanel.ShowMetas(self.metadata)

    def write_xmldata(self):
        self.update_metadata()
        metadatadict=self.metadata.toPlain()  # text-script REQUIRED VALUE JJM 29/12/2024 
        if metadatadict['text:script']=='':
            # wx.MessageBox('text:script is not set, please check in the Texte panel', 'value required', wx.OK | wx.ICON_INFORMATION)
            wx.MessageBox('Le Type d\'écriture (text:script) doit être précisé, vérifier dans l\'onglet Texte ', 'value required', wx.OK | wx.ICON_INFORMATION)
            return
        tempout = tempfile.NamedTemporaryFile(delete=False)
        # self.io.write(tempout.name, metadata=self.metadata.toPlain())
        self.io.write(tempout.name, metadata=metadatadict)
        
        tempout.close()
        outfile = os.path.join(self.dirname, self.filename)
        shutil.copyfile(tempout.name, outfile)
        #print("tempout.name: ",tempout.name)
        os.unlink(tempout.name)
    
    def OnRetainToggled(self, e):
        self.cleanup = not self.cleanup

    def OnConfigSelected(self, e):
        if self.filename:
            self.FileOpenedError(e)
        else:
            global confpath
            confpath = e.GetPath()

            # self.SetTitle("["+confpath+"]")          # JJM 26/12/2024
            myconfig = wx.Config.Get()
            myconfig.Write("meta/confpath",confpath) # JJM 26/12/2024
            myconfig.Flush()

            self.config = MetaConfig(confpath)
            if len(self.metapanels) > 0:
                self.clear_metapanels()
            self.draw_metapanels()

    def FileOpenedError(self,e):
        dlg = wx.MessageDialog(self, 'Error: please close the file first.', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def NoFileError(self,e):
        dlg = wx.MessageDialog(self, 'Error: no file opened!', 'No file opened', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnExit(self,e):
        self.Close(True)

    def OnOpen(self,e):
        """ Open a file"""
        if not self.config:
            self.NoFileError(e)
            return False
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "meta files (txt/html)|*.html;*.txt", wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = dlg.GetPath()
            self.filename = os.path.basename(self.infile)
            self.dirname = os.path.dirname(self.infile)
            infile = os.path.join(self.dirname, self.filename)
            self.parse_file(infile)
            if self.cleanup:
                self.clear_metapanels()
                self.draw_metapanels()
                self.update_interface()
            self.filepanel.control.SetValue(self.txt)
            # global confpath
            # self.SetTitle("["+confpath+"]   -   "+self.filename)  # added JJM 26/12/2024
            self.SetTitle("Meta : "+self.filename)  # added JJM 30/12/2024
        dlg.Destroy()

    def OnSave(self,e):
        if not self.filename:
            self.NoFileError(e)
            return
        if os.path.splitext(self.filename)[1] in ['.html', '.xhtml', '.xml']:
            self.write_xmldata()
        else:
            self.OnSaveAs(e)

    def OnSaveAs(self,e):
        if not self.filename:
            self.NoFileError(e)
        else:
            xfilename = os.path.splitext(self.filename)[0]

            dlg = wx.FileDialog(self, "Choose a file", self.dirname, xfilename, "*.html", wx.FD_SAVE)
            if dlg.ShowModal() == wx.ID_OK:
                self.outfile = dlg.GetPath()
                self.filename = os.path.basename(self.outfile)
                self.dirname = os.path.dirname(self.outfile)
                if not os.path.splitext(self.filename)[1] == '.html':
                    self.filename = ''.join([self.filename, os.path.extsep, 'html'])
                with open(os.path.join(self.dirname, self.filename), 'w', encoding='utf-8') as xhtml:
                    self.write_xmldata()
            dlg.Destroy()

    def OnClose(self,e):
        self.OnSave(e)
        self.init_values()
        #   JJM save window position and size
        x,y=self.Position 
        w,h=self.Size
        self.myconfig.WriteInt("MainFrame/pos/x",x)
        self.myconfig.WriteInt("MainFrame/pos/y",y)
        self.myconfig.WriteInt("MainFrame/size/w",w)
        self.myconfig.WriteInt("MainFrame/size/h",h)
        self.myconfig.Flush()  # permanently writes
        if self.cleanup:
            self.clear_metapanels()
            self.draw_metapanels()
        self.filepanel.control.SetValue('')


def main():
    #confname = 'meta.xml'
    #metaconfig = MetaConfig(confname)
    app = wx.App()
    frame = MainFrame(None, title="Bamana corpus metaeditor")
    frame.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
