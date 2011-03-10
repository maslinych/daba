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
        for md in self.xml.findall('head/meta'):
            name = md.get('name')
            if name is not None:
                self.metadata.append((name, md.get('content')))
        self.para = [i.text or ''.join([j.text for j in i.findall('span') if j.get('class') == 'sent']) for i in self.xml.findall('body/p')]

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
                        variant = False
                        for gloss in glosslist:
                            if not variant:
                                try:
                                    w = gloss.html()
                                except AttributeError:
                                    print tokvalue
                                w.tail = '\n'
                                variant=True
                            else:
                                #NB: SIDE EFFECT!
                                w.append(gloss.html(variant=True))
                                w.tail = '\n'
                        annot.append(w)
            body.append(par)
        self.xml = root

    def write(self):
        e.ElementTree(self.xml).write(self.filename, self.encoding)

