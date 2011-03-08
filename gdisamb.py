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
        'PUNCT',
        ]

def makeGlossString(gloss, morphemes=False):
    if not ''.join(gloss.ps) and not gloss.gloss and not gloss.morphemes:
        return gloss.form
    elif morphemes and gloss.morphemes:
        return u'{0} ({1}){3}{2}{4}'.format(gloss.form, '/'.join(gloss.ps), gloss.gloss, os.linesep, '\n' + os.linesep.join([unicode(m) for m in gloss.morphemes]))
    else:
        return u'{0} ({1}){3}{2}'.format(gloss.form, '/'.join(gloss.ps), gloss.gloss, os.linesep)

def makeGlossSfm(gloss):
    sfm = ur"""
\lx {0}
\ps {1}
\ge {2}
""".format(gloss.form, '/'.join(gloss.ps), gloss.gloss)
    for m in gloss.morphemes:
        sfm = sfm + r'\mm ' + ':'.join([gloss.form, '/'.join(gloss.ps), gloss.gloss]) + os.linesep
    return sfm

def makeHtmlAnnotation(annotlist, root=None):
    if root:
        annot = root
        annot.clear()
        annot.attrib['class'] = 'annot'
    else:
        annot = e.Element('span', {'class': 'annot'})
    for glosslist in annotlist:
        if len(glosslist) == 1 and 'PUNCT' in glosslist[0].ps:
            c = e.SubElement(annot, 'span', {'class': 'c'})
            c.text = glosslist[0].form
        else:
            annot.append(glosslist[0].html())
            if len(glosslist) > 1:
                for gloss in glosslist[1:]:
                    annot[-1].append(gloss.html(variant=True))
    return annot


class FileParser(object):
    def __init__(self):
        self.xml = None
        self.glosses = []
        self.txt = ''
        self.dirty = False

    def read_file(self, filename):
        self.xml = e.parse(filename)
        self.txt = []
        for p in self.xml.findall('body/p'):
            annot = None
            for sent in p.findall('span'):
                if sent.attrib['class'] == 'sent':
                    for span in sent.findall('span'):
                        if span.attrib['class'] == 'annot':
                            annot = span
                    stup = parse_sent(sent) + (annot, len(self.glosses))
                    self.glosses.append(stup)
                    self.txt.append(stup[0])

    def write(self, filename):
        self.xml.write(filename)



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
            self.parent.parent.sentpanel.OnSaveResults(event)
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
        addb.Bind(wx.EVT_BUTTON, self.OnAddMorpheme)

        vbox_top.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0)
        self.SetSizer(vbox_top)

        if self.form in self.parent.parent.parent.parent.localdict:
            self.SetGloss(self.parent.parent.parent.parent.localdict[self.form])

    def SetGloss(self, gloss):
        self.form.SetValue(gloss.form)
        self.ps.SetCheckedStrings(gloss.ps)
        self.gloss.SetValue(gloss.gloss)

    def GetGloss(self):
        form = self.form.GetValue()
        ps = set(self.ps.GetCheckedStrings())
        gloss = self.gloss.GetValue()
        morphemes = tuple(self.morphemes)
        return Gloss(form, ps, gloss, morphemes)

    def SaveGloss(self):
        self.parent.parent.parent.parent.localdict[self.form] = makeGlossSfm(self.GetGloss())

    def OnAddMorpheme(self, event):
        if PSLIST[0] is not 'mrph':
            PSLIST.insert(0, 'mrph')
        dlg = GlossInputDialog(self.GetParent(), -1, "Add morpheme", pos=map(lambda x: x+20, self.GetPositionTuple()) )
        if (dlg.ShowModal() == wx.ID_OK):
            self.morphemes.append(dlg.GetGloss())


class GlossEditButton(wx.Panel):
    def __init__(self, parent, gloss, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.gloss = gloss
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
        dlg.SetGloss(self.gloss)
        if (dlg.ShowModal() == wx.ID_OK):
            dlg.SaveGloss()
            self.parent.OnEdition(dlg.GetGloss())
        dlg.Destroy()

    def OnStateChange(self, statecode, gloss):
        glossstring = makeGlossString(gloss, morphemes=True)
        self.button.SetLabel(glossstring)
        self.Layout()
        self.parent.Layout()
        self.parent.parent.Layout()
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
        self.parent = parent
        self.children = []

        if self.vertical:
            self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            self.sizer = wx.BoxSizer(wx.VERTICAL)

        #FIXME: should I keep token string and use it here in spite of glosslist's first form?
        if len(glosslist) > 1:
            self.gloss = Gloss(glosslist[0].form, set([]), '', ())
            self.statecode = 2
        elif ''.join(glosslist[0].ps) in ['', None, '<?>'] and glosslist[0].gloss in ['', None, '<?>']:
            self.gloss = Gloss(glosslist[0].form, set([]), '', ())
            self.statecode = -1
        else:
            self.gloss = glosslist[0]
            self.statecode = 1
        
        self.UpdateState(self.statecode, self.gloss)

        self.sizerflags = (wx.EXPAND | wx.TOP | wx.BOTTOM, 4)
        self.sizer.Add(self.mbutton, 0, *self.sizerflags)

        self.AddButtons(self.glosslist)

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
            elif len(self.selectlist) == 1:
                self.statecode = 0
                self.gloss = self.selectlist[0]
                self.mbutton.gloss = self.selectlist[0]
            elif len(self.selectlist) == 0:
                self.statecode = 2
                self.gloss = Gloss(self.children[0].gloss.form, set([]), '', ())
            else:
                print "Bug: Negative selection!", selected
        else:
            self.gloss = gloss
            self.glosslist = [gloss]
            self.selectlist = [gloss]
            self.statecode = 0
        self.UpdateState(self.statecode, self.gloss)


class SentenceAnnotation(wx.ScrolledWindow):
    def __init__(self, parent, senttuple, vertical=True, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.vertical = vertical
        self.children = []
        self.parent = parent

        if vertical:
            self.Sizer = wx.BoxSizer(wx.VERTICAL)
        else:
            self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        for glosslist in senttuple[1]:
            abox = GlossSelector(self, glosslist, vertical=self.vertical)
            self.children.append(abox)
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
    def __init__(self, parent, senttuple=('', (), None), vertical=True, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)
        self.senttuple = senttuple
        self.vertical = vertical
        self.parent = parent
        self.selectlist = []
        self.localdict = {}
        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        #self.SetSizer(self.Sizer)

    def ShowSent(self, sent):
        self.senttuple = sent
        self.selectlist = []
        self.Sizer.Clear(deleteWindows=True)
        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        sentfont = wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)

        self.sentsource = wx.StaticText(self, -1, self.senttuple[0])
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
        self.annotlist = SentenceAnnotation(self, self.senttuple, vertical=self.vertical)
        self.Sizer.Add(self.annotlist, 1, wx.EXPAND)
        self.Sizer.Fit(self)
        self.SetSizer(self.Sizer)
        self.Layout()

    def PrevSentence(self, event):
        self.OnSaveResults(event)
        self.ShowSent(self.parent.processor.glosses[self.senttuple[3]-1])
        self.parent.Layout()

    def NextSentence(self, event):
        self.OnSaveResults(event)
        try:
            self.ShowSent(self.parent.processor.glosses[self.senttuple[3]+1])
        except IndexError:
            self.ShowSent(self.parent.processor.glosses[0])
        self.parent.Layout()

    def OnSaveResults(self, event):
        for selector in self.annotlist.children:
            if selector.selectlist:
                self.parent.processor.dirty = True
            self.selectlist.append(selector.selectlist or selector.glosslist)
        #NB: operates by SIDE EFFECT on MainFrame().processor.xml
        makeHtmlAnnotation(self.selectlist, root=self.senttuple[2])
        self.parent.processor.glosses[self.senttuple[3]] = tuple([self.senttuple[0], self.selectlist, self.senttuple[2], self.senttuple[3]])


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
        self.Bind(wx.EVT_MENU, self.OnVerticalMode, menuVertical)
        menuBar.Append(settingsmenu,"&Settings") # Adding the "filemenu" to the MenuBar
        self.SetMenuBar(menuBar)  # Adding the MenuBar to the Frame content.

        self.dirname = os.curdir
        self.infile = None
        self.outfile = None
        self.dictfile = 'localdict.txt'
        self.processor = FileParser()
        self.filepanel = FilePanel(self)
        self.sentpanel = SentPanel(self)

        self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.Sizer.Add(self.sentpanel, 2, wx.EXPAND)
        self.Sizer.Add(self.filepanel, 1, wx.EXPAND)
        self.SetSizer(self.Sizer)
        self.Show()

    def OnVerticalMode(self,e):
        self.sentpanel.vertical = not self.sentpanel.vertical
        #FIXME: redraw here current sentence
        self.sentpanel.Layout()
        self.sentpanel.Refresh()
        self.Layout()

    def OnExit(self,e):
        if self.processor.dirty:
            self.OnSave(e)
        self.Close(True)

    def OnOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            self.processor.read_file(self.infile)
            self.filepanel.ShowFile(t[0] for t in self.processor.glosses)
            self.sentpanel.ShowSent(self.processor.glosses[0])
            self.Layout()
        dlg.Destroy()

    def SaveFiles(self,e):
        if self.sentpanel.localdict:
            with open(self.dictfile, 'a+') as d:
                d.write(u'\n\n'.join(self.sentpanel.localdict.values()).encode('utf-8'))
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

