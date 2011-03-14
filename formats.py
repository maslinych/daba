#!/usr/bin/env python
# -*- coding: utf-8 -*-

## FIXME: add copyright notice

import os
import re
import xml.etree.cElementTree as e
from ntgloss import Gloss

# Data structure for internal bare text representation:
# ({metadata}, [para+])

# Data structure for parsed text representation:
# ({metadata}, [_para [_sent (text, [_c|w|t|comment ]) ] ])
# w: (token, stage, [Gloss()])
# c: (token,)
# t: (start|end|tag, name)
# comment: (text,)

class BaseReader(object):
    def data(self):
        return (self.metadata, self.para)

class TxtReader(BaseReader):
    def __init__(self, filename, encoding="utf-8"):
        self.metadata = []
        with open(filename) as f:
            self.para = re.split(os.linesep + '{2,}', f.read().decode(encoding).strip())

class HtmlReader(BaseReader):
    def __init__(self, filename):
        tree = e.ElementTree()
        self.xml = tree.parse(filename)
        self.metadata = []
        self.para = []
        self.glosses = []
        for md in self.xml.findall('head/meta'):
            name = md.get('name')
            if name is not None:
                self.metadata.append((name, md.get('content')))
        #self.para = [i.text or ''.join([j.text for j in i.findall('span') if j.get('class') == 'sent']) for i in self.xml.findall('body/p')]
        def elem_to_gloss(xgloss):
            morphemes = []
            if xgloss.attrib['class'] in ['lemma', 'm', 'lemma var']:
                form = xgloss.text
                ps = set([])
                gloss = ''
                for i in xgloss.getchildren():
                    if i.attrib['class'] == 'ps':
                        ps = set(i.text.split('/'))
                    elif i.attrib['class'] == 'gloss':
                        gloss = i.text
                    elif i.attrib['class'] == 'm':
                        morphemes.append(elem_to_gloss(i))
            return Gloss(form, ps, gloss, tuple(morphemes))

        def parse_sent(sent):
            text = sent.text
            annot = []
            for span in sent.findall('span'):
                if span.attrib['class'] == 'annot':
                    for w in span.findall('span'):
                        if w.attrib['class'] == 'w':
                            #, 'c']:
                            for lem in w.findall('span'):
                                if lem.attrib['class'] == 'lemma':
                                    glosslist = []
                                    glosslist.append(elem_to_gloss(lem))
                                    for var in lem.findall('span'):
                                        if var.attrib['class'] == 'lemma var':
                                            glosslist.append(elem_to_gloss(var))
                            annot.append(('w', (w.text, w.attrib['stage'], glosslist)))
                        elif w.attrib['class'] == 'c':
                            annot.append((w.attrib['class'], w.text))
                        elif w.attrib['class'] == 't':
                            annot.append(('Tag', w.text))
                        elif w.attrib['class'] == 'comment':
                            annot.append(('Comment', w.text))
            return (text, annot)

        for p in self.xml.findall('body/p'):
            self.para.append(p.text or ''.join([j.text for j in p.findall('span') if j.get('class') == 'sent']))
            par = []
            for sent in p.findall('span'):
                if sent.attrib['class'] == 'sent':
                    par.append(parse_sent(sent))
            self.glosses.append(par)

class HtmlWriter(object):
    def __init__(self, (metadata, para), filename, encoding="utf-8"):
        self.encoding = encoding
        self.metadata = metadata
        self.para = para
        self.filename = filename

        self.stylesheet = """
      body { font-size: 120%; }
      span.w, span.c { color: #444; font-size: 14px; display: inline-block; float: none; vertical-align: top; padding: 3px 10px 10px 0; }
      span.m { color: red; font-size: 14px; display: block; float: left; vertical-align: top; padding: 3px 10px 10px 0; }
      span.sent { clear: left; display: inline; float: none; padding: 3px 3px 3px 0; }
      span.annot { clear: left; display: block; float: none; padding: 3px 3px 3px 0; }
      sub       { color: #606099; font-size: 12px; display: block; vertical-align: top; }
      sub.lemma, sub.gloss { white-space: nowrap; }
      span.lemma.var { clear: left; display: block; margin-top: 2px; padding-top: 2px; border-top: 2px solid #EEE; }
      p { margin-bottom: 8px; }
      p { vertical-align: top; }

        """

        root = e.Element('html')
        head = e.SubElement(root, 'head')
        meta = e.SubElement(head, 'meta', {'http-equiv': 'Content-Type', 'content': 'text/html; charset={0}'.format(self.encoding)})
        for (name, content) in metadata:
            md = e.SubElement(head, 'meta', {'name': name, 'content': content})
        body = e.SubElement(root, 'body')
        style = e.SubElement(head, 'style', {'type': 'text/css'})
        style.text = self.stylesheet

        def gloss_to_html(gloss, spanclass='lemma', variant=False):
            if variant:
                spanclass = 'lemma var'
            w = e.Element('span', {'class': spanclass})
            
            w.text = gloss.form
            if gloss.ps:
                ps = e.SubElement(w, 'sub', {'class': 'ps'})
                ps.text = '/'.join(gloss.ps)
            if gloss.gloss:
                ge = e.SubElement(w, 'sub', {'class':'gloss'})
                ge.text = gloss.gloss

            for m in gloss.morphemes:
                #NB: SIDE EFFECT!
                w.append(gloss_to_html(m, spanclass='m'))
            return w


        for para in self.para:
            par = e.Element('p')
            for (senttext, sentannot) in para:
                st = e.SubElement(par, 'span', {'class': 'sent'})
                st.text = senttext
                st.tail = '\n'
                annot = e.SubElement(st, 'span', {'class':'annot'})
                annot.tail = '\n'
                for (toktype, tokvalue) in sentannot:
                    if toktype in ['Comment']:
                        c = e.SubElement(annot, 'span', {'class': 'comment'})
                        c.text = tokvalue
                        c.tail = '\n'
                    elif toktype in ['Tag']:
                        t = e.SubElement(annot, 'span', {'class': 't'})
                        t.text = tokvalue
                        t.tail = '\n'
                    elif toktype in ['c']:
                        c = e.SubElement(annot, 'span', {'class':'c'})
                        c.text = tokvalue
                        c.tail = '\n'
                    elif toktype in ['w']:
                        sourceform, stage, glosslist = tokvalue
                        w = e.SubElement(annot, 'span', {'class':'w', 'stage':unicode(stage)})
                        w.text = sourceform
                        variant = False
                        for gloss in glosslist:
                            if not variant:
                                l = gloss_to_html(gloss)
                                l.tail = '\n'
                                variant=True
                            else:
                                #NB: SIDE EFFECT!
                                l.append(gloss_to_html(gloss, variant=True))
                                l.tail = '\n'
                        w.append(l)
            body.append(par)
        self.xml = root

    def write(self):
        e.ElementTree(self.xml).write(self.filename, self.encoding)

