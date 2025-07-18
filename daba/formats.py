#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Library for input/output formats supported by Daba
#
# Copyright (C) 2010—2021  Kirill Maslinsky <kirill@altlinux.org>
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

# Data structure for internal bare text representation:
# ({metadata}, [para+])

# Data structure for parsed text representation:
# ({metadata}, [_para [_sent (text, [_c|w|t|comment ]) ] ])
# w: (token, stage, [Gloss()])
# c: (token,)
# t: (start|end|tag, name)
# comment: (text,)

import os
import re
import codecs
import unicodedata
import hashlib
import xml.etree.ElementTree as e
from pytrie import StringTrie as trie
from collections import defaultdict, OrderedDict
from collections.abc import MutableMapping
from abc import abstractmethod

import daba.grammar
from daba.ntgloss import Gloss, __str__
from daba.orthography import detone

#FIXME: duplicate, move to common util
normalizeText = lambda t: unicodedata.normalize('NFKD', str(t))

# to allow pickling polisemy dictionary
def ddlist():
    return defaultdict(list)

def gloss_to_html(gloss, spanclass='lemma', variant=False):
    if variant:
        spanclass = 'lemma var'
    w = e.Element('span', {'class': spanclass})
    try:
        w.text = gloss.form
    except AttributeError:
        print(u"ERR: {}".format(gloss))
        exit(1)
    if gloss.ps:
        ps = e.SubElement(w, 'sub', {'class': 'ps'})
        ps.text = '/'.join(gloss.ps)
    if gloss.gloss:
        ge = e.SubElement(w, 'sub', {'class':'gloss'})
        ge.text = gloss.gloss

    try:
        for m in gloss.morphemes:
            #NB: SIDE EFFECT!
            w.append(gloss_to_html(m, spanclass='m'))
    except AttributeError:
        print("ERR GLOSS: {}\n".format(str(gloss)))
    return w


def glosstext_to_html(glosstext, variant=False, **kwargs):
    """Serialize text representation of a gloss into HTML string"""
    toks = daba.grammar.str_tokenize(glosstext)
    gloss = daba.grammar.stringgloss_parser().parse(toks)
    html = gloss_to_html(gloss, variant=variant)
    return e.tostring(html, **kwargs)


class BaseToken(object):
    def __str__(self):
        return u' '.join([self.type, self.value or '', str(self.attrs)])

    def __repr__(self):
        return ' '.join([self.type, repr(self.value), str(self.attrs)])

    def as_tuple(self):
        return (self.type, self.value)

    @abstractmethod
    def __eq__(self, other):
        pass

    @abstractmethod
    def matches(self, other):
        pass

    @abstractmethod
    def union(self, other):
        pass


class PlainToken(BaseToken):
    def __init__(self, toktuple=None, attrs=None):
        if toktuple:
            self.type, self.value = toktuple
        else:
            self.type, self.value = '', ''
        self.token = self.value
        self.stage = ''
        self.gloss = Gloss(self.token, (), self.type, ())
        self.glosslist = [self.gloss]
        self.attrs = attrs
        
    def __eq__(self, other):
        if self.type == other.type:
            if not self.gloss and not other.gloss:
                return True
            else:
                return self.value == other.value
        return False

    def matches(self, other):
        if self.type == other.type:
            if other.value:
                try:
                    return re.match(other.value, self.value)
                except TypeError:
                    print("Failed MATCH: {} ~ /{}/".format(repr(self.value), repr(other.value)))
            else:
                return True
        return False

    def union(self, other):
        gt = self
        if self.type == other.type:
            if other.value:
                gt = PlainToken((other.type, other.value))                
            else:
                gt = PlainToken((other.type, self.value))
        return gt


class WordToken(BaseToken):
    """wrapper object holding all data related to a word token"""
    def __init__(self, glosslist, token=None, stage='', attrs=None):
        self.type = 'w'
        self.glosslist = glosslist
        self.gloss = glosslist[0]
        if token:
            self.token = token
        else:
            self.token = self.gloss.form
        self.stage = stage
        self.value = self.token, self.stage, self.glosslist
        self.attrs = attrs

    def __eq__(self, other):
        if other.type == 'w':
            return self.glosslist == other.glosslist
        return False

    def __str__(self):
        return u' '.join([self.type, self.stage, str(self.gloss)])

    def as_tuple(self):
        # SUSPECT! to remove?
        return (self.type, (self.token, self.stage, self.glosslist))

    def matches(self, other):
        if other.type == 'w':
            return self.gloss.matches(other.glosslist[0], psstrict=True)
        return False

    def union(self, other):
        gt = self
        if other.type == 'w':
            if other.gloss:
                newgloss = self.glosslist[0].union(other.gloss, psoverride=False)
                gt = WordToken([newgloss], self.token, other.stage)
        return gt

    def setGlosslist(self, glosslist):
        self.glosslist = glosslist
        self.value = self.token, self.stage, self.glosslist


class BaseReader(object):
    def data(self):
        return (self.metadata, self.para)


class TxtReader(BaseReader):
    def __init__(self, filename, encoding="utf-8"):
        self.isdummy = True
        self.metadata = {}
        with open(filename, encoding=encoding) as f:
            self.para = re.split(os.linesep + '{2,}', normalizeText(f.read().strip()))


class SentenceListReader(BaseReader):
    def __init__(self, filename, encoding="utf-8"):
        self.isdummy = True
        self.metadata = {}
        sent_re = r'(?P<starttag><s[ ]+n="(?P<id>[0-9]+)"\s*>)(?P<senttext>(.|\n(?!<s n=))*)(?P<endtag></s>)'
        out = []
        with open(filename, encoding=encoding) as f:
            txt = f.read()
            for s in re.finditer(sent_re, txt, re.MULTILINE):
                s_text = s.group('senttext')
                out.append(s_text)
        self.para = [out]


class HtmlCommons(object):
    def __init__(self):
        self.tmap = {'Comment': 'comment',
        'Tag': 't',
        'c': 'c',
        '</s>': 'sent'}
        self.invmap = {v: k for k, v in self.tmap.items()}

    def token_type_to_html_class(self, tstring):
        try:
            return self.tmap[tstring]
        except KeyError:
            return tstring

    def html_class_to_token_type(self, tstring):
        try:
            return self.invmap[tstring]
        except KeyError:
            return tstring


class HtmlReader(BaseReader):
    def __init__(self, filename, onlymeta=False, compatibility_mode=True):
        self.filename = filename
        self.onlymeta = onlymeta
        self.metadata = OrderedDict()
        self.para = []
        self.numwords = 0
        self.numsent = 0
        self.numpar = 0
        self.isdummy = False
        self.tokens = []
        self.sentences = []
        self.iterparse()
        if compatibility_mode:
            self.glosses = self.make_compatible_glosses(self.tokens)
        for k, v in [
                ('_auto:words', self.numwords),
                ('_auto:sentences', self.numsent),
                ('_auto:paragraphs', self.numpar)
                ]:
            self.metadata[k] = str(v)

    def __iter__(self):
        for token in self.tokens:
            yield token

    def iterparse(self):
        glosslist = []
        sentlist = []
        for event, elem in e.iterparse(self.filename, events=('start', 'end'), parser=e.XMLParser(encoding="utf-8")):
            if event == 'start':
                if elem.tag == 'p':
                    self.tokens.append(PlainToken(('<p>', None)))
                    continue
                elif elem.tag == 'span' and elem.get('class') == 'sent':
                    self.tokens.append(PlainToken(('<s>', None)))
                    continue
                else:
                    continue
            if elem.tag == 'meta':
                name = elem.get('name')
                if name is not None:
                    self.metadata[name] = elem.get('content')
            elif elem.tag == 'p':
                if elem.text:
                    self.isdummy = True
                    partext = normalizeText(elem.text)
                else:
                    partext = u' '.join(sentlist)
                self.para.append(partext)
                self.tokens.append(PlainToken(('</p>', partext)))
                self.numpar += 1
                sentlist = []
            elif elem.tag in ['span']:
                spanclass = elem.get('class')
                elemtext = normalizeText(elem.text) or ''
                if spanclass == 'w':
                    try:
                        self.tokens.append(
                            WordToken(glosslist, token=elemtext, stage=elem.get('stage'), attrs=elem.attrib)
                        )
                    except IndexError:
                        print(elem, sentlist)
                    glosslist = []
                    self.numwords += 1
                elif spanclass in ['lemma var'] and not self.onlymeta:
                    glosslist.append(self.elem_to_gloss(elem))
                elif spanclass in ['lemma'] and not self.onlymeta:
                    glosslist.insert(0, self.elem_to_gloss(elem))
                elif spanclass in ['m', 'annot']:
                    continue
                else:
                    self.tokens.append(
                        self._make_plain_token(elem.attrib, elemtext)
                    )
                    if spanclass == 'sent':
                        sentlist.append(elemtext)
                        self.numsent += 1

    def _make_plain_token(self, attrs, elemtext):
        elemclass = attrs.pop('class', '')
        toktype = HtmlCommons().html_class_to_token_type(elemclass)
        return PlainToken((toktype, elemtext), attrs=attrs)        

    def make_compatible_glosses(self, tokens):
        glosses = []
        par = []
        sentannot = []
        for gt in tokens:
            if gt.type == '</p>':
                glosses.append(par)
                par = []
            elif gt.type == '</s>':
                par.append((gt, sentannot))
                sentannot = []
            elif gt.type in ['<s>', '<p>']:
                continue
            else:
                sentannot.append(gt)
        return glosses

    def elem_to_gloss(self, xgloss):
        form = normalizeText(xgloss.text)
        ps = ()
        gloss = ''
        morphemes = []
        for sub in list(xgloss):
            subclass = sub.get('class')
            if subclass == 'ps':
                ps = tuple(filter(None, sub.text.split('/')))
            elif subclass == 'gloss':
                gloss = normalizeText(sub.text)
            elif subclass == 'm':
                morphemes.append(self.elem_to_gloss(sub))
        return Gloss(form, ps, gloss, tuple(morphemes))

    def parse_sent(self, sent, onlymeta=False):
        text = normalizeText(sent.text)
        annot = []
        for span in sent.findall('span'):
            if span.attrib['class'] == 'annot':
                for w in span.findall('span'):
                    if w.attrib['class'] == 'w':
                        #, 'c']:
                        self.numwords += 1
                        if onlymeta:
                            continue
                        for lem in w.findall('span'):
                            if lem.attrib['class'] == 'lemma':
                                glosslist = []
                                glosslist.append(self.elem_to_gloss(lem))
                                for var in lem.findall('span'):
                                    if var.attrib['class'] == 'lemma var':
                                        glosslist.append(self.elem_to_gloss(var))
                        annot.append(('w', (normalizeText(w.text), w.attrib['stage'], glosslist)))
                    elif w.attrib['class'] == 'c':
                        annot.append((w.attrib['class'], w.text or ''))
                    elif w.attrib['class'] == 't':
                        annot.append(('Tag', w.text or ''))
                    elif w.attrib['class'] == 'comment':
                        annot.append(('Comment', normalizeText(w.text) or ''))
        return (text, annot)

    # DEPRECATED, should be removed soon
    def setgloss(self, gloss, index):
        pp, sp, tp, gp = index
        self.glosses[pp][sp][1][tp][1][2][gp] = gloss


class TxtWriter(object):
    def __init__(self, metadata_para, filename, encoding="utf-8"):
        metadata, para = metadata_para
        self.encoding = encoding
        self.metadata = metadata
        self.para = para
        self.filename = filename

    def write(self):
        with open(self.filename, 'w', encoding=self.encoding) as outfile:
            for p in self.para:
                prevtype = None
                for (senttoken, sentannot) in p:
                    for gt in sentannot:
                        if gt.type == 'w':
                            sourceform, stage, glosslist = gt.value
                            if not prevtype == 'copen' and prevtype is not None:
                                outfile.write(u" ")
                            outfile.write(sourceform)
                            prevtype = gt.type
                        elif gt.type == 'c':
                            prevtype = gt.type
                            if gt.value in u'.,:;!?»)]}':
                                outfile.write(gt.value)
                            else:
                                outfile.write(u' {}'.format(gt.value))
                                if gt.value in u'([{«':
                                    prevtype = 'copen'
                        else:
                            outfile.write(u" {}".format(gt.value))
                            prevtype = gt.type
                outfile.write("\n\n")


class TokensWriter(object):
    def __init__(self, metadata_para, filename, encoding="utf-8"):
        metadata, para = metadata_para
        self.encoding = encoding
        self.metadata = metadata
        self.para = para
        self.filename = filename

    def write(self):
        with open(self.filename, 'w', encoding=self.encoding) as outfile:
            outfile.write(u'# <doc path={}'.format(self.filename))
            for (name, content) in self.metadata.items():
                outfile.write(u' {}={}'.format(name, content))
            outfile.write(u'>\n')
            for p in self.para:
                for (senttoken, sentannot) in p:
                    for gt in sentannot:
                        if gt.type == 'w':
                            token = detone(gt.gloss.form)
                            if gt.token.isupper():
                                token = token.upper()
                            elif gt.token.istitle():
                                token = token[0].upper() + token[1:]
                        else:
                            token = gt.value
                        outfile.write(u'{}\n'.format(token))
                    outfile.write("\n")
                outfile.write("\n")


class SentenceListWriter(object):
    def __init__(self, metadata_para, filename, encoding="utf-8"):
        metadata, para = metadata_para
        self.encoding = encoding
        self.metadata = metadata
        self.para = para
        self.filename = filename

    def write(self):
        with open(self.filename, 'w', encoding=self.encoding) as outfile:
            snum = 0
            for p in self.para:
                for (senttoken, sentannot) in p:
                    s = u"<s n={0}>{1}</s>\n".format(snum, senttoken.value.strip())
                    outfile.write(s)
                    snum += 1
                outfile.write("\n")
        

class SimpleHtmlWriter(object):
    def __init__(self, metadata_para, filename, encoding="utf-8"):
        metadata, para = metadata_para
        self.encoding = encoding
        self.metadata = metadata
        self.para = para
        self.filename = filename

        html = e.Element('html')
        head = e.SubElement(html, 'head')
        e.SubElement(head, 'meta', {'http-equiv': "Content-Type", 'content': "text/html; charset={0}".format(self.encoding)})
        # what about sorting metadata by key ? sortedmetadata=dict(sorted(metadata.items()))
        for (name, content) in self.metadata.items():
            md = e.SubElement(head, 'meta', {'name': name, 'content': content})
        body = e.SubElement(html, 'body')
        for p in para:
            if p:
                para = e.SubElement(body, 'p')
                para.text = p
        self.xml = html

    def write(self):
        e.ElementTree(self.xml).write(self.filename, self.encoding)


class HtmlWriter(object):
    def __init__(self, metadata_para, filename=None, encoding="utf-8",
                 compatibility_mode=True):
        metadata, para = metadata_para
        self.encoding = encoding
        self.metadata = metadata
        self.para = para
        self.filename = filename

        root = self._make_header()
        if compatibility_mode:
            self._make_xml_compat(root)
        else:
            self._make_xml(root)

    def _make_header(self):
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
        # what about sorting metadata by key ? sortedmetadata=dict(sorted(metadata.items()))
        for (name, content) in self.metadata.items():
            md = e.SubElement(head, 'meta', {'name': name, 'content': content})
        style = e.SubElement(head, 'style', {'type': 'text/css'})
        style.text = self.stylesheet
        return root

    def _format_plain_token(self, annot, gt):
        gtclass = HtmlCommons().token_type_to_html_class(gt.type)
        attrs = {'class': gtclass}
        if gt.attrs:
            attrs.update(gt.attrs)
        tok = e.SubElement(annot, 'span', attrs)
        tok.text = gt.value
        tok.tail = '\n'
        return tok

    def _format_word_token(self, annot, gt):
        sourceform, stage, glosslist = gt.value
        w = e.SubElement(annot, 'span', {'class': 'w',
                                         'stage': str(stage)})
        w.text = gt.token
        w.tail = '\n'
        variant = False
        for gloss in glosslist:
            if not variant:
                lem = gloss_to_html(gloss)
                variant = True
            else:
                #NB: SIDE EFFECT!
                lem.append(gloss_to_html(gloss, variant=True))
        w.append(lem)
        return w

    def _make_xml_compat(self, root):
        body = e.SubElement(root, 'body')
        for para in self.para:
            par = e.Element('p')
            for (senttoken, sentannot) in para:
                st = self._format_plain_token(par, senttoken)
                annot = e.SubElement(st, 'span', {'class': 'annot'})
                annot.tail = '\n'
                for gt in sentannot:
                    if gt.type == 'w':
                        w = self._format_word_token(annot, gt)
                    else:
                        tok = self._format_plain_token(annot, gt)
            body.append(par)
        self.xml = root

    def _make_xml(self, root):
        body = e.SubElement(root, 'body')
        for gt in self.para:
            if gt.type == '<p>':
                par = e.SubElement(body, 'p')
            elif gt.type == '<s>':
                annot = e.Element('span', {'class': 'annot'})
            elif gt.type == '</s>':
                sent = self._format_plain_token(par, gt)
                sent.append(annot)
            elif gt.type == '</p>':
                continue
            elif gt.type == 'w':
                w = self._format_word_token(annot, gt)
            else:
                tok = self._format_plain_token(annot, gt)
        self.xml = root

    def write(self):
        if self.filename:
            e.ElementTree(self.xml).write(self.filename, self.encoding)


class FileWrapper(object):
    def __init__(self, encoding='utf-8'):
        self.encoding = encoding
        self.output_formats = ["html", "txt", "sentlist", "tokens"]

    def read(self, filename, sentlist=False):
        try:
            basename, ext = os.path.splitext(filename)
        except (AttributeError):
            print("FILENAME", filename)
        if ext in ['.txt']:
            if sentlist:
                self.format = 'sentlist'
                self._reader = SentenceListReader(filename)
            else:
                self.format = 'txt'
                self._reader = TxtReader(filename)
        elif ext in ['.html', '.htm']:
            self.format = 'html'
            self._reader = HtmlReader(filename)
        else:
            raise ValueError("Unknown file extention: ", ext)
        self.metadata, self.para = self._reader.data()
        if self._reader.isdummy:
            self.parsed = False
            self.glosses = self.para
        else:
            self.parsed = True
            self.glosses = self._reader.glosses

    def write(self, filename, result=None, metadata=None, parsed=None, format="html"):
        if result is None:
            result = self.glosses
        if metadata is None:
            metadata = self.metadata
        if parsed is None:
            parsed = self.parsed
        if format == "html":
            if parsed:
                HtmlWriter((metadata, result), filename, self.encoding).write()
            else:
                SimpleHtmlWriter((metadata, result), filename, self.encoding).write()
        elif format == "sentlist":
            SentenceListWriter((metadata, result), filename, self.encoding).write()
        elif format == "txt":
            TxtWriter((metadata, result), filename, self.encoding).write()
        elif format == "tokens":
            TokensWriter((metadata, result), filename, self.encoding).write()
        else:
            print("Unknown output format: {}".format(format))


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
            # example str(gloss): álalandiya:n:piété3 [álalandi:n:personne.pieuse [Ála:n:Dieu landi:adj:qui.aime] ya:mrph:ABSTR]
            sfm="\n\\lx "+gloss.form
            sfm+="\n\\ps "+'/'.join(gloss.ps)
            sfm+="\n\\gf "+gloss.gloss
            if gloss.morphemes:
                lxroot,mrphx=str(gloss).split(" ",1)
                sfm+=mmlist(str(mrphx[1:-1]))
            sfm+="\n"
            return sfm
            
        def mmlist(mrphx): # can handle multiple level mm ( source: wordparser1 )
            mrphx=mrphx.replace("[","[ ")
            mrphx=mrphx.replace("]"," ]")
            mrphelem=mrphx.split(" ")
            mmprefix="\n\\mm"
            level=0
            mms=""
            for elem in mrphelem:
                if elem=="[":
                    level+=1
                    mmprefix=mmprefix+"m"
                elif elem=="]":
                    level-=1
                    mmprefix=mmprefix[:-1]
                else:
                    if ":" in elem:
                        mmlx,mmps,mmgloss=elem.split(":",2)
                        mms+=mmprefix+" "+mmlx+":"+mmps+":"+mmgloss  # or tomonolith(mmgloss) ?
                    else:
                        mms+=mmprefix+" "+elem   # ??? what happened ???
            return mms+"\n"


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

class DabaDict(MutableMapping):
    def __init__(self):
        self._data = trie({})
        self.lang = None
        self.name = None
        self.ver = None
        self.sha = hashlib.sha1()
        self._hashed = None

    @property
    def description(self):
        return ' '.join([self.lang, self.name, self.ver])

    @property
    def hash(self):
        if not self.sha:
            return self._hashed
        else:
            return self.sha.hexdigest()

    def __repr__(self):
        return ' '.join((self.lang, self.name, self.ver, self.hash))

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return self._data.__iter__()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        assert isinstance(value, Gloss)
        self.sha.update(repr((key,value)).encode('utf-8'))
        return self._data.setdefault(key, []).append(value)

    def __delitem__(self, key):
        return self._data.__delitem__(key)

    def __eq__(self, other):
        return all([getattr(self, a) == getattr(other, a) for a in ('lang', 'name', 'ver', 'hash')])

    def __getstate__(self):
        if self.sha:
            self._hashed = self.sha.hexdigest()
            self.sha = None
        return self.__dict__

    def attributed(self):
        return all([self.lang, self.name, self.ver])

    def iter_prefixes(self, string):
        return self._data.iter_prefixes(string)


class VariantsDict(MutableMapping):
    def __init__(self, canonical=False):
        self._data = defaultdict(list)
        self.canonical = canonical

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        for (ps, gs), formlist in self._data.items():
            for form in formlist:
                yield Gloss(form, ps, gs, ())

    def __getitem__(self, gloss):
        form, ps, gs, ms = gloss
        lookup = []
        if gs:
            lookup.append((form, (ps, gs)))
        if ms:
            stems = [m for m in ms if 'mrph' not in m.ps]  # tried replace by JJM - tried keepmrph first
            # stems = [m for m in ms ]   # JJ removed: if 'mrph' not in m.ps
            if len(stems) == 1:
                g = stems[0]
                lookup.append((g.form, (g.ps, g.gloss)))
        for f, lkp in lookup:
            try:
                variants = self._data[lkp]
                for varlist in variants:
                    if f in varlist:
                        if self.canonical:
                            return varlist[0]
                        else:
                            return varlist
            except KeyError:
                pass
        return []

    def __setitem__(self, gloss, value):
        assert isinstance(value, set)
        key = (gloss.ps, gloss.gloss)
        self._data[key] = value.add(gloss.form)

    def add(self, glosslist):
        f, ps, gs, ms = glosslist[0]
        self._data[(ps, gs)].append([gloss.form for gloss in glosslist])

    def __delitem__(self, gloss):
        form, ps, gs, ms = gloss
        index = (ps, gs)
        self._data[index].remove(form)
        if not self._data[index]:
            self._data.__delitem__(index)
        return


class DictReader(object):
    def __init__(self, filename, encoding='utf-8', store=True,
                 variants=False, polisemy=False, keepmrph=False,
                 normalize=True, ignorelist=('i'), inverse=False, 
                 lemmafields=('lx', 'le', 'va'),  # JJM changed 'va',) to 'va')
                 variantfields=('vc', 'a'), # JJM removed 've', 28/12/2024 'vt', 06/04/2025 (but consequences if has mm: aded to lx/va twice! see edit 26-06-2025)
                 conditionalavoidfields=('ve'),   # JJM added 06/01/2025
                 glossfields=('gf', 'ge', 'gr', 'dff'), canonical=False):
        # JJM moved va vt from variantfields to lemmafields as per our discussion 17 jan 2022
        # JJM added 'gr' to glossfields (malidaba) 22/6/2024
        # JJM question : are gvf gve gvr relevant here (gvf should be for polysemy)
        # JJM 28/12/2024 remove 've' completely, not wanted as possible choice in gdisamb: kó = gó 
        #            IMPORTANT! : 've' moved to ignorelist / existings tests and paragraphs about 've' to be ignored
        #            06/01/2025: rolled back!
        # JJM 06/01/2025 've' conditional avoid fields ("variants to avoid"): 
        #     important to keep for gparser to guess. Example twa = tɔgɔ (bam)
        #     but some introduce too much unwanted ambiguity : 
        #         Example (bam) : kó ve of gó (bad) as there are already other legitimate "ko" (lemmafields)
        #     => need to create a first pass to load all values of lemmafields in a list (avoidlist)
        #     then in 2d (normal) pass, check if ve already in avoidlist, then avoid, else add
        #     This handling is not ideal : 
        #     One could with that "a man ko" would display ve "ko" (="go") if preceded by "man" or "ka"
        #     but this sentence analysis is beyond the scope of gparser

        self._dict = DabaDict()
        self._variants = VariantsDict(canonical=canonical)
        self._polisemy = defaultdict(ddlist)
        self.keepmrph = keepmrph
        self.normalize = normalize
        self.line = 0
        self.ignorelist = ignorelist
        self.inverse = inverse
        self.lemmafields = lemmafields
        self.variantfields = variantfields
        self.conditionalavoidfields = conditionalavoidfields
        self.glossfields = glossfields
        ignore = False
        lemmalist = []
        key = None
        ps = ()
        glossdict = {}
        lemma = None

        def parsemm(v):
            try:
                f, p, g = v.split(':')
                if p:
                    ps = tuple(p.split('/'))
                else:
                    ps = ()
                return Gloss(f, ps, g, ())
            except (ValueError):
                print("Error line:", str(self.line), str(v))

        def normalize(value):
            try:
                #return normalizeText(value.translate({ord(u'.'): None, ord(u'-'):None}).lower())   # JJM removes lower
                return normalizeText(value.translate({ord(u'.'): None, ord(u'-'):None}))
            except AttributeError:
                return value

        def make_item(value, key=None):
            """return [key, Gloss] for lemmalist with unannotated Gloss object
            
            key — optional key (standardized lemma) to use instead of the current wordform
"""
            if self.normalize:
                key = normalize(key)
                value = normalize(value)
            if not key:
                key = value
            return [key, Gloss(form=value, ps=(), gloss="", morphemes=())]

        def push_items(primarykey, lemmalist):
            for key, lx in lemmalist:
                self._dict[key] = lx
                detonedkey = detone(key)
                if not detonedkey == key:
                    self._dict[detonedkey] = lx

        def select_gloss(glossdict):
            ge = ''
            for f in self.glossfields:
                try:
                    ge = glossdict[f]
                    break
                except KeyError:
                    pass
            return ge

        def process_record(key, lemmalist, ps, glossdict):
            """parse one toolbox lexical entry and add to a DabaDict

            key — lookup form for DabaDict
            lemmalist — list of gloss objects collected from a lexical entry
            ps — part of speech tag
            glossdict — all possible glosses collected from a lexical entry
"""
            if lemmalist:
                ge = select_gloss(glossdict)
                if self.inverse:
                    key = u'_'.join(['/'.join(ps), ge])
                    lemmalist = [(key, g._replace(ps=ps, gloss=ge)) for k, g in lemmalist]
                    push_items(key, lemmalist)
                else:
                    lemmalist = [(key, item._replace(ps=ps, gloss=ge)) for key, item in lemmalist]
                    if not ps == ('mrph',) or self.keepmrph:
                        if store:
                            push_items(key, lemmalist)
                        if variants and len(lemmalist) > 1:
                            self._variants.add(list(zip(*lemmalist))[1])

        with codecs.open(filename, 'r', encoding=encoding) as dictfile:
            # print("open 1st pass:",filename)
            # first  pass: created avoid list later used to filter through conditionalavoidfields
            avoidlist=[]
            for line in dictfile:
                if line.startswith('\\'): 
                    #line = unicodedata.normalize('NFKD', line) = normalizeText
                    tag, space, value = line[1:].partition(' ')
                    value = value.strip() 
                    if tag in self.lemmafields:
                        value = normalizeText(value)
                        if value not in avoidlist:
                            avoidlist.append(value)

            # normal pass:
        with codecs.open(filename, 'r', encoding=encoding) as dictfile:
            # print("open 2d pass:",filename)
            mmlevel=0
            morphemetext=""
            key=""
            for line in dictfile:
                self.line = self.line + 1
                # end of the article/dictionary
                if not line or line.isspace():
                    if key and not ignore:
                        lemmalist2=[] # build lemmalist2 with key and Gloss
                        for x in lemmalist:
                            lkey=x[0]
                            lxkey=lkey
                            if ":" in lkey: lkey,lxkey=lkey.split(":",1)  # special case generated by 've'
                            morphemetext=x[1] 
                            if morphemetext:
                                #balance closing brackets
                                nrb=morphemetext.count("]")
                                nlb=morphemetext.count("[")
                                if nlb > nrb:
                                    morphemetext+="]"*(nlb-nrb)
                                # elif nlb < nrb : # should not happen

                                morphemetext=morphemetext.replace(" ]","]").strip()
                                morphemetext=" ["+morphemetext+"]"
                            morphemetext=lxkey+":"+pstext+":"+glosstext+morphemetext
                                
                            # morpheme as a Gloss
                            #print("morphemetext:",morphemetext)
                            try:
                                toks = daba.grammar.str_tokenize(morphemetext)
                                g = daba.grammar.stringgloss_parser().parse(toks)
                            except:
                                #print("erreur de mm sur : ",morphemetext)
                                continue

                            lemmalist1=[]
                            lemmalist1.append(lkey)
                            lemmalist1.append(g)
                            lemmalist2.append(lemmalist1)
                            
                        process_record(key, lemmalist2, ps, glossdict)

                    mmlevel=0
                    morphemetext=""

                    ignore = False
                    lemmalist = []
                    ps = ()
                    glosstext=""
                    glossdict = {}
                    key = None
                    lemma = None
                    
                elif line.startswith('\\'):
                    # line = unicodedata.normalize('NFKD', line)
                    tag, space, value = line[1:].partition(' ')
                    value = value.strip()
                    if tag in glossfields:
                        value = unicodedata.normalize('NFC',value)
                    else:
                        value = normalizeText(value)  

                    if tag in ['lang', 'ver', 'name']:
                        self._dict.__setattr__(tag, value)

                    elif tag in self.ignorelist:
                        ignore = True

                    elif tag in self.lemmafields:
                        if self.normalize:
                            key = normalize(value)
                        else:
                            key = value
                        
                        if " " in key : 
                            key=key.replace(" "," ")  # replace by hard space (cf enciclop "famous names")
                            # print("\033[1mILLEGAL\033[0m space in ",key," replaced by hard space")

                        lemmalist1=[]
                        lemmalist1.append(key)
                        lemmalist1.append('')  # Gloss in text form (morphemes)
                        lemmalist.append(lemmalist1)
                        morphemetext=""
                        mmlevel=0
                        ignoremm=False

                    elif tag in self.variantfields and tag not in self.conditionalavoidfields:  # ve should inherit gloss from lx
                        if " " in value : 
                            value=value.replace(" "," ")  # replace by hard space (cf enciclop "famous names")
                            # print("\033[1mILLEGAL\033[0m space in ",key," '",tag,"' variant for ",value," replaced by hard space")
                        lemmalist1=[]
                        lemmalist1.append(value)
                        lemmalist1.append('')  # Gloss in text form (morphemes)
                        lemmalist.append(lemmalist1)
                        # print("va? lemmalist:",lemmalist)
                        morphemetext=""
                        mmlevel=0
                        ignoremm=False
                        #else:
                            # shouldn't happen: variant should not come before lemma
                            #lemmalist.append(make_item(value))

                    elif tag in self.conditionalavoidfields:
                        if value not in avoidlist:
                            # print("add ve:",value)
                            if " " in value : 
                                value=value.replace(" "," ")  # replace by hard space (cf enciclop "famous names")
                                # print("\033[1mILLEGAL\033[0m space in ",key," 've' variant for ",value," replaced by hard space")
                            try:
                                lemmalist1=[]
                                #lemmalist1.append(value)   # try: value+":"+key and split before process to keep key ? (check for ":" in lkey string)
                                lemmalist1.append(value+":"+key) # tried lemmalist1.append("?"+value+":"+key)= never picked in gparser
                                lemmalist1.append(lemmalist[0][1])  # inherits lx gloss
                                lemmalist.append(lemmalist1)
                                # print("ve? lemmalist:",lemmalist)
                                #      [['gó', ''], ['kó:gó', '']]
                            except:
                                print("error / value, key",value,key)
                        ignoremm=True

                    elif tag=="vt": # JJM 26-06-2025 side effect of removing vt from variantfields
                        morphemetext=""
                        mmlevel=0
                        ignoremm=True

                    elif tag.startswith("mm") and not ignoremm : # caveat : supposed to be something like "mmmm" BUT could be as well "mmaa"
                        morphemetext=""
                        thislevel=len(tag)-2
                        if mmlevel<thislevel: # not relevant for level 0 !
                            morphemetext+="["
                        elif mmlevel>thislevel:
                            morphemetext+="]"*(mmlevel-thislevel)+" "
                        mmlevel=thislevel
                        morphemetext+=value+" "
                        lemmalist[-1][1] = lemmalist[-1][1]+morphemetext

                    elif tag in ['ps'] and not ps:
                        if value:
                            ps = tuple(value.split('/'))
                            pstext=value
                        else:
                            ps = ()

                    elif tag in self.glossfields:

                        if " " in value : 
                            value=value.replace(" ",".")
                            # print("\033[1mILLEGAL\033[0m space in gloss for ",key," replaced by dot:",value)

                        glossdict[tag] = value
                        if tag=="gf": glosstext=value    # otherwise the last glossfields will be published, eg russian!

                    elif tag in ['gv','gvf']: # JJM added gvf 22/6/24
                        if polisemy:
                            self._polisemy[key][select_gloss(glossdict)].append(value)
                            dk = detone(key)
                            if not dk == key:
                                self._polisemy[dk][select_gloss(glossdict)].append(value)

            else:  # when the for loop is finished, do the following (last line)
                if key and not ignore:
                    lemmalist2=[] # build lemmalist2 with key and Gloss
                    for x in lemmalist:
                        lkey=x[0]
                        lxkey=lkey
                        if ":" in lkey: lkey,lxkey=lkey.split(":",1)  # special case generated by conditionalavoidfields
                        morphemetext=x[1] 
                        if morphemetext:
                            if mmlevel!=0:
                                morphemetext+="]"*mmlevel
                            morphemetext=morphemetext.replace(" ]","]").strip()
                            morphemetext=" ["+morphemetext+"]"
                        morphemetext=lxkey+":"+pstext+":"+glosstext+morphemetext
                            
                        # morpheme as a Gloss
                        try:
                            toks = daba.grammar.str_tokenize(morphemetext)
                            g = daba.grammar.stringgloss_parser().parse(toks)
                        except:
                            # print("ERR erreur de mm sur : ",morphemetext)
                            continue
                        lemmalist1=[]
                        lemmalist1.append(key)
                        lemmalist1.append(g)
                        lemmalist2.append(lemmalist1)
                        
                    process_record(key, lemmalist2, ps, glossdict)

            if not self._dict.attributed():
                print(r"Dictionary does not contain obligatory \lang, \name or \ver fields.\
                        Please specify them and try to load again.")
                print(self._dict.lang, self._dict.name, self._dict.ver)
            

    #FIXME: kept for backward compatibility, remove after refactoring
    def values(self):
        try:
            return (self._dict.hash, self._dict.lang, self._dict.name, self._dict.ver, self._dict)
        except AttributeError:
            return (None, None, None, None, {})

    def get(self):
        return self._dict

    def getVariants(self):
        return self._variants

    def getPolisemy(self):
        return self._polisemy
