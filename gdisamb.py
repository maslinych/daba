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
import wx.lib.scrolledpanel as scrolled
import wx.combo
from wx.lib.stattext import GenStaticText
import os
import formats
import datetime
import codecs
import unicodedata
import xml.etree.cElementTree as e
from ntgloss import Gloss, emptyGloss
import grammar
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError

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
                    #FIXME: remove when GlossedText interface is ready
                    token = formats.GlossToken(glosstoken)
                    if token.type == 'w':
                        token.glosslist = selectlist
                    outgloss.append(token)
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

## CONFIG

class DabaConfig(object):
    def __init__(self):
        self._cfgdata = wx.Config('gdisamb')
        self.font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        if self._cfgdata.Exists('font'):
            self.font.SetNativeFontInfoUserDesc(self._cfgdata.Read('font'))
        if self._cfgdata.Exists('vertical'):
            self.vertical = self._cfgdata.ReadBool('vertical')
        else:
            self.vertical = True

    def save(self, key=None):
        self._cfgdata.Write('font', self.font.GetNativeFontInfoUserDesc())
        self._cfgdata.WriteBool('vertical', self.vertical)


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
        self.parent = parent
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
            self.toktype, (self.form, self.stage, self.glosslist) = glosstoken.as_tuple()
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

        if self.vertical:
            self.sizer = wx.BoxSizer(wx.VERTICAL)
        else:
            self.sizer = wx.BoxSizer(wx.HORIZONTAL) 


        #FIXME: should I keep token string and use it here in spite of glosslist's first form?
        if len(self.glosslist) > 1:
            self.gloss = Gloss(self.form, set([]), '', ())
            self.statecode = 2
        elif ''.join(self.glosslist[0].ps) in ['', None, '<?>'] and self.glosslist[0].gloss in ['', None, '<?>'] and not self.glosslist[0].morphemes:
            self.gloss = Gloss(self.glosslist[0].form, set([]), '', ())
            self.statecode = -1
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
        oldgloss = self.gloss
        self.gloss = gloss
        self.glosslist = [gloss] + [button.gloss for button in self.children]
        selectedbuttons = [button.gloss for button in self.children if button.selected]
        if selectedbuttons:
            self.selectlist = [gloss] + selectedbuttons
        else:
            self.selectlist = [gloss]
        self.statecode = 0
        self.UpdateState(self.statecode, self.gloss)
        self.logger.LogEdit(oldgloss, self.gloss)

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
        self.logger.LogJoin((firsttoken[1][0],nexttoken[1][0]), newform)

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
        self.searchfield = NormalizedTextCtrl(self, -1, searchstr)
        sizer.Add(wx.StaticText(self, -1, "Search for word or part of word:"))
        sizer.Add(self.searchfield)
        self.typefield = wx.RadioBox(self, -1, "Search type", wx.DefaultPosition, wx.DefaultSize, ['word part', 'sentence part'], 1)
        sizer.Add(self.typefield)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(sizer)

    def GetSearchString(self):
        return self.searchfield.GetValue()

    def GetSearchType(self):
        return self.typefield.GetStringSelection()

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
        self.index = index
        self.selectlist = selectlist
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.token = formats.GlossToken(token)
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
        dlg.Destroy()

    def GetToken(self):
        return self.token.as_tuple()


class SentenceAnnotation(wx.Window):
    def __init__(self, parent, sentglosses, sentselect, vertical=True, *args, **kwargs):
        wx.Window.__init__(self, parent, *args, **kwargs)
        self.vertical = vertical
        self.children = []

        if vertical:
            self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            self.Sizer = wx.BoxSizer(wx.VERTICAL) 
        for (index, (glosstoken,selectlist)) in enumerate(zip(sentglosses,sentselect)):
            if glosstoken.type == 'w':
                abox = GlossSelector(self, index, glosstoken, selectlist, vertical=self.vertical)
            else:
                abox = TokenEditButton(self, index, glosstoken, selectlist)
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


class SentPanel(wx.ScrolledWindow):
    'Manual disambiguation panel'
    def __init__(self, parent, vertical=True, *args, **kwargs):
        wx.ScrolledWindow.__init__(self, parent, *args, **kwargs)
        self.SetScrollRate(20, 20)
        self.vertical = vertical
        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.savedstate = None
        self.isshown = False
        self.sentfont = self.GetFont()
        self.sentfont.SetPointSize(self.sentfont.GetPointSize() + 2)

        # create navigation buttons
        prevbutton = wx.Button(self, -1, '<')
        prevbutton.Bind(wx.EVT_BUTTON, self.PrevSentence)
        nextbutton = wx.Button(self, -1, '>')
        nextbutton.Bind(wx.EVT_BUTTON, self.NextSentence)
        savebutton = wx.Button(self, -1, 'Save results')
        savebutton.Bind(wx.EVT_BUTTON, self.OnSaveResults)
        navsizer = wx.BoxSizer(wx.HORIZONTAL)
        navsizer.Add(prevbutton, 0)
        navsizer.Add(nextbutton, 0)
        navsizer.Add(savebutton, 0, wx.ALIGN_RIGHT)
        self.Sizer.Add(navsizer, 0, wx.EXPAND)
        self.sentsizer = wx.BoxSizer(wx.VERTICAL)
        self.Sizer.Add(self.sentsizer, 0, wx.EXPAND)
        self.SetSizer(self.Sizer)
        self.Layout()

    def ShowSent(self, senttuple, snum):
        self.senttext, self.selectlist, self.tokenlist, self.sentindex = senttuple
        if self.isshown:
            self.sentsizer.Remove(self.sentsource)
            self.sentsource.Destroy()
            self.sentsizer.Remove(self.annotlist)
            self.annotlist.Destroy()
        self.snum = snum
        self.sentsource = wx.StaticText(self, -1, self.senttext.replace('\n', ' '))
        self.sentsource.SetFont(self.sentfont)
        self.sentsource.SetForegroundColour('Navy')
        sentwidth = self.GetClientSize().GetWidth()-5
        self.sentsource.Wrap(sentwidth)
        self.sentsizer.Add(self.sentsource, 1, wx.EXPAND)
        self.annotlist = SentenceAnnotation(self, self.tokenlist, self.selectlist, vertical=self.vertical)
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
        tokenlist = []
        self.selectlist = []
        for selector in self.annotlist.children:
            if selector.selectlist:
                self.GetTopLevelParent().processor.dirty = True
            self.selectlist.append(selector.selectlist)
            tokenlist.append(selector.GetToken())
        self.GetTopLevelParent().processor.glosses[self.snum] = tuple([self.senttext, self.selectlist, tokenlist, self.sentindex])


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
        menuClose = filemenu.Append(wx.ID_CLOSE,"C&lose","Close current file")
        self.Bind(wx.EVT_MENU,self.OnClose, menuClose)
        menuSearch = filemenu.Append(wx.ID_FIND,"F&ind","Find text")
        self.Bind(wx.EVT_MENU, self.OnSearch, menuSearch)
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


        # constants, no need to reinit on opening next file
        self.dirname = os.curdir
        self.dictfile = 'localdict.txt'
        self.config = DabaConfig()
        self.SetFont(self.config.font)
        self.InitValues()


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
        self.logger = None
        self.searchstr = ""
        self.fileopened = False

    def InitUI(self):
        self.splitter = wx.SplitterWindow(self)
        self.filepanel = FilePanel(self.splitter)
        self.sentpanel = SentPanel(self.splitter, vertical=self.config.vertical)
        self.splitter.SplitVertically(self.sentpanel, self.filepanel)
        self.splitter.SetSashGravity(0.95)
        self.splitter.SetMinimumPaneSize(20)
        self.splitter.SetSashSize(5)
        self.Sizer.Add(self.splitter, 1, wx.EXPAND)
        self.Layout()

    def CleanUI(self):
        self.splitter.Destroy()

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
        self.config.vertical = not self.config.vertical
        self.config.save()
        if self.fileopened:
            self.UpdateUI()

    def OnSelectFont(self,e):
        fontdata = wx.FontData()
        fontdata.SetInitialFont(self.config.font)

        dlg = wx.FontDialog(self, fontdata)
        if dlg.ShowModal() == wx.ID_OK:
            fontdata = dlg.GetFontData()
            self.config.font = fontdata.GetChosenFont()
            self.config.save()
            self.SetFont(self.config.font)
            if self.fileopened:
                self.UpdateUI()
        dlg.Destroy()

    def OnWidgetInspector(self, e):
        import wx.lib.inspection
        wx.lib.inspection.InspectionTool().Show()

    def OnUndoTokens(self,e):
        savedstate = self.sentpanel.savedstate
        if savedstate:
            snum = self.sentpanel.snum
            self.processor.glosses[snum] = savedstate
            self.sentpanel.ShowSent(savedstate, snum)
            savedstate = None
        else:
            print "No undo information"

    def OnSearch(self,e):
        dlg = SearchDialog(self, -1, "Search word", self.searchstr)
        if (dlg.ShowModal() == wx.ID_OK):
            self.searchstr = dlg.GetSearchString()
            searchtype = dlg.GetSearchType()

        if not self.searchstr:
            return
        for snum, sent in enumerate(self.processor.glosses):
            if snum > self.sentpanel.snum:
                if searchtype == 'word part':
                    for word in sent[2]:
                        try:
                            if self.searchstr in formats.GlossToken(word).token:
                                self.sentpanel.ShowSent(sent, snum)
                                break
                        except (AttributeError):
                            print word
                    else:
                        continue

                elif searchtype == 'sentence part':
                    if self.searchstr in sent[0]:
                        self.sentpanel.ShowSent(sent, snum)
                    else:
                        continue

                break

        else:
            notf = NotFoundDialog(self, -1, "Not found", self.searchstr)
            notf.ShowModal()

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

    def OnOpen(self,e):
        """ Open a file"""
        dlg = wx.FileDialog(self, "Choose a file", self.dirname, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.infile = dlg.GetPath()
            self.dirname = os.path.dirname(self.infile)
            logfile = os.path.extsep.join([get_basename(self.infile), 'log'])
            self.logger = EditLogger(logfile)
            self.processor.read_file(self.infile)
            self.InitUI()
            self.filepanel.ShowFile(t[0] for t in self.processor.glosses)
            self.sentpanel.ShowSent(self.processor.glosses[0], 0)
            self.fileopened = True
            self.Layout()
        dlg.Destroy()

    def SaveFiles(self,e):
        if self.localdict:
            formats.DictWriter(self.localdict, self.dictfile, lang='default', name='localdict',ver='0').write()
        self.processor.write(self.outfile)


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

