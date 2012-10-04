#!/usr/bin/env python
# -*- coding: utf-8 -*-

## FIXME: add copyright notice

import os
import re
import codecs
import unicodedata
import hashlib
import xml.etree.cElementTree as e
from ntgloss import Gloss
from orthography import detone
from pytrie import StringTrie as trie
from collections import namedtuple

# Data structure for internal bare text representation:
# ({metadata}, [para+])

# Data structure for parsed text representation:
# ({metadata}, [_para [_sent (text, [_c|w|t|comment ]) ] ])
# w: (token, stage, [Gloss()])
# c: (token,)
# t: (start|end|tag, name)
# comment: (text,)

#FIXME: duplicate, move to common util
normalizeText = lambda t: unicodedata.normalize('NFKD', unicode(t))

class GlossToken(object):
    def __init__(self, toktuple=None):
        if toktuple:
            self.type, self.value = toktuple
        else:
            self.type, self.value = '', ''
        if self.type == 'w':
            self.token, self.stage, self.glosslist = self.value
            self.gloss = self.glosslist[0]
        else:
            self.token = self.value
            self.stage = ''
            self.gloss = Gloss(self.token, set(), self.type, ())
            self.glosslist = [self.gloss]
     
    def as_tuple(self):
        if self.type == 'w':
            return (self.type, (self.token, self.stage, self.glosslist))
        else:
            return (self.type, self.value)

class BaseReader(object):
    def data(self):
        return (self.metadata, self.para)

class TxtReader(BaseReader):
    def __init__(self, filename, encoding="utf-8"):
        self.metadata = []
        with open(filename) as f:
            self.para = re.split(os.linesep + '{2,}', normalizeText(f.read().decode(encoding).strip()))

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
                form = normalizeText(xgloss.text)
                ps = set([])
                gloss = ''
                for i in xgloss.getchildren():
                    if i.attrib['class'] == 'ps':
                        ps = set(i.text.split('/'))
                    elif i.attrib['class'] == 'gloss':
                        gloss = normalizeText(i.text) 
                    elif i.attrib['class'] == 'm':
                        morphemes.append(elem_to_gloss(i))
            return Gloss(form, ps, gloss, tuple(morphemes))

        def parse_sent(sent):
            text = normalizeText(sent.text)
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
                            annot.append(('w', (normalizeText(w.text), w.attrib['stage'], glosslist)))
                        elif w.attrib['class'] == 'c':
                            annot.append((w.attrib['class'], w.text or ''))
                        elif w.attrib['class'] == 't':
                            annot.append(('Tag', w.text or ''))
                        elif w.attrib['class'] == 'comment':
                            annot.append(('Comment', normalizeText(w.text) or ''))
            return (text, annot)

        for p in self.xml.findall('body/p'):
            self.para.append(p.text or ''.join([normalizeText(j.text) for j in p.findall('span') if j.get('class') == 'sent']))
            par = []
            for sent in p.findall('span'):
                if sent.attrib['class'] == 'sent':
                    par.append(parse_sent(sent))
            self.glosses.append(par)

    def itergloss(self):
        for pp, par in enumerate(self.glosses):
            for sp, sent in enumerate(par):
                for tp, tok in enumerate(sent[1]):
                    token = GlossToken(tok)
                    if token.type == 'w':
                        for gp, gloss in enumerate(token.glosslist):
                            yield (gloss, (pp, sp, tp, gp))

    def setgloss(self, gloss, index):
        pp, sp, tp, gp = index
        self.glosses[pp][sp][1][tp][1][2][gp] = gloss


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
      span.lemma, span.lemma.var { clear: left; display: block; margin-top: 2px; padding-top: 2px; border-top: 2px solid #EEE; }
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


class DictWriter(object):
    def __init__(self, udict, filename, lang='', name='', ver='', add=False, encoding='utf-8'):
        self.lang = lang
        self.name = name
        self.ver = ver
        self.udict = udict
        self.filename = filename
        self.encoding = encoding
        self.add = add

    def write(self):
        def makeGlossSfm(gloss,morpheme=False):
            if not morpheme:
                sfm = ur"""
\lx {0}
\ps {1}
\ge {2}
                """.format(gloss.form, '/'.join(gloss.ps), gloss.gloss)
                for m in gloss.morphemes:
                    sfm = sfm + makeGlossSfm(m, morpheme=True)
            else:
                sfm = r'\mm ' + ':'.join([gloss.form, '/'.join(gloss.ps), gloss.gloss]) + os.linesep
            return sfm

        with codecs.open(self.filename, 'w', encoding=self.encoding) as dictfile:
            dictfile.write(u'\\lang {0}\n'.format(self.lang))
            dictfile.write(u'\\name {0}\n'.format(self.name))
            dictfile.write(u'\\ver {0}\n'.format(self.ver))
            wordlist = []
            for glosslist in self.udict.values():
                for gloss in glosslist:
                    if gloss not in wordlist:
                        wordlist.append(gloss)
            #FIXME: poor man's ordering of dictionary articles
            wordlist.sort()
            for gloss in wordlist:
                dictfile.write(makeGlossSfm(gloss))


class DictReader(object):
    def __init__(self, filename,encoding='utf-8'):

        def parsemm(v):
            f, p, g = v.split(':')
            if p:
                ps = p.split('/')
            else:
                ps = []
            return Gloss(f, set(ps), g, ())

        def push_items(d, l, ps=frozenset([]), ge=''):
            for k, i in l:
                lx = i._replace(ps=ps,gloss=ge)
                d.setdefault(k,[]).append(lx)
                detoned = detone(k)
                if not detoned == k:
                    d.setdefault(detoned,[]).append(lx)

        findict = trie({})
        sha = hashlib.sha1()
        ids = {}
        tlist = []
        key = None
        ps = set()
        ge = ''

        with codecs.open(filename, 'r', encoding=encoding) as dictfile:
            for line in dictfile:
                sha.update(repr(line))
                if not line or line.isspace():
                    if tlist and not ps == set(['mrph']):
                        push_items(findict, tlist, ps, ge)
                    tlist = []
                    ps = set()
                    ge = ''
                    key = None

                elif line.startswith('\\'):
                    tag, space, value = line[1:].partition(' ')
                    value = value.strip()
                    if tag in ['lang', 'ver', 'name']:
                            ids[tag] = value
                    if tag in ['lx', 'le', 'va', 'vc']:
                        key = normalizeText(value.translate({ord(u'.'):None,ord(u'-'):None}).lower())
                        tlist.append([key, Gloss(form=value,ps=set([]),gloss="",morphemes=())])
                    if tag in ['mm']:
                        tlist[-1][1] = tlist[-1][1]._replace(morphemes=tlist[-1][1].morphemes+(parsemm(value),))
                    if tag in ['ps'] and not ps:
                        if value:
                            ps = set(value.split('/'))
                        else:
                            ps = set([])
                    if tag in ['ge'] and not ge:
                        ge = value
                else:
                    if tlist:
                        push_items(findict, tlist, ps, ge)

            self.hash = sha.hexdigest()
            try:
                self.lang = ids['lang']
                self.name = ids['name']
                self.ver = ids['ver']
            except KeyError:
                print r"Dictionary does not contain obligatory \lang, \name or \ver fields.\n\
                        Please specify them and try to load again."
            self.udict = findict
            
    def values(self):
        try:
            return (self.hash, self.lang, self.name, self.ver, self.udict)
        except AttributeError:
            return (None, None, None, None, {})

