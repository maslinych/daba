#!/usr/bin/env python
# -*- coding: utf-8 -*-

## FIXME: add copyright notice

import os
import re
import codecs
import unicodedata
import hashlib
import xml.etree.cElementTree as e
import grammar
from ntgloss import Gloss
from orthography import detone
from pytrie import StringTrie as trie
from collections import namedtuple, MutableMapping, defaultdict, OrderedDict

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

# to allow pickling polisemy dictionary
def ddlist():
    return defaultdict(list)

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

def glosstext_to_html(glosstext, variant=False, **kwargs):
    """Serialize text representation of a gloss into HTML string"""
    toks = grammar.str_tokenize(glosstext)
    gloss = grammar.stringgloss_parser().parse(toks)
    html = gloss_to_html(gloss, variant=variant)
    return e.tostring(html, **kwargs)


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
            self.gloss = Gloss(self.token, (), self.type, ())
            self.glosslist = [self.gloss]
     
    def __unicode__(self):
        return u' '.join(self.type, self.token)

    def __repr__(self):
        return ' '.join([self.type, repr(self.token), repr(self.value)])

    def as_tuple(self):
        if self.type == 'w':
            return (self.type, (self.token, self.stage, self.glosslist))
        else:
            return (self.type, self.value)

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
        with open(filename) as f:
            self.para = re.split(os.linesep + '{2,}', normalizeText(f.read().decode(encoding).strip()))


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
        #self.glosses = []
        self.iterparse()
        if compatibility_mode:
            self.glosses = self.make_compatible_glosses(self.tokens)
        for k,v in [ 
                ('_auto:words', self.numwords),
                ('_auto:sentences', self.numsent),
                ('_auto:paragraphs', self.numpar)
                ]:
            self.metadata[k] = unicode(v)

    def __iter__(self):
        for token in self.tokens:
            yield token

    def iterparse(self):
        glosslist = []
        sentlist = []
        for event, elem in e.iterparse(self.filename):
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
                self.tokens.append(GlossToken(('p', partext)))
                self.numpar += 1
            elif elem.tag in ['span', 'sub']:
                spanclass = elem.get('class')
                elemtext = normalizeText(elem.text) or ''
                if spanclass == 'sent':
                    sentlist.append(elemtext)
                    self.tokens.append(GlossToken(('s', elemtext)))
                    self.numsent += 1
                elif spanclass == 'c':
                    self.tokens.append(GlossToken(('c', elemtext)))
                elif spanclass == 't':
                    self.tokens.append(GlossToken(('Tag', elemtext)))
                elif spanclass == 'comment':
                    self.tokens.append(GlossToken(('Comment', elemtext)))
                elif spanclass == 'w':
                    self.tokens.append(GlossToken(('w', (elemtext, elem.get('stage'), glosslist))))
                    glosslist = []
                    self.numwords += 1
                elif spanclass in ['lemma var'] and not self.onlymeta:
                    glosslist.append(self.elem_to_gloss(elem))
                elif spanclass in ['lemma'] and not self.onlymeta:
                    glosslist.insert(0, self.elem_to_gloss(elem))
                if spanclass not in ['m', 'gloss', 'ps', 'lemma', 'lemma var']:
                    elem.clear()

    def make_compatible_glosses(self, tokens):
        glosses = []
        par = []
        sentannot = []
        for gt in tokens:
            if gt.type == 'p':
                glosses.append(par)
                par = []
            elif gt.type == 's':
                par.append((gt.value, sentannot))
                sentannot = []
            else:
                sentannot.append(gt)
        return glosses
                           
    def _iterparse(self):
        par = []
        partext = []
        stext = []
        for event, elem in e.iterparse(self.filename):
            if elem.tag == 'meta':
                name = elem.get('name')
                if name is not None:
                    self.metadata[name] = elem.get('content')
            elif elem.tag == 'p':
                self.numpar += 1
                self.glosses.append(par)
                self.para.append(' '.join(stext))
                par = []
                stext = []
                partext.append(elem.text)
                elem.clear()
            elif elem.tag == 'span' and elem.get('class') == 'sent':
                self.numsent += 1
                if elem.text is not None:
                    stext.append(elem.text)
                senttext, annot = self.parse_sent(elem, onlymeta=self.onlymeta)
                self.sentences.append(senttext)
                par.append((senttext, annot))
                elem.clear()
        if not ''.join(self.para):
            self.para = partext
            self.isdummy = True

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



class SimpleHtmlWriter(object):
    def __init__(self, (metadata, para), filename, encoding="utf-8"):
        self.encoding = encoding
        self.metadata = metadata
        self.para = para
        self.filename = filename

        html = e.Element('html')
        head = e.SubElement(html, 'head')
        e.SubElement(head, 'meta', {'http-equiv': "Content-Type", 'content': "text/html; charset={0}".format(self.encoding)})
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
        for (name, content) in metadata.items():
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
                for gt in sentannot:
                    if gt.type in ['Comment']:
                        c = e.SubElement(annot, 'span', {'class': 'comment'})
                        c.text = gt.value
                        c.tail = '\n'
                    elif gt.type in ['Tag']:
                        t = e.SubElement(annot, 'span', {'class': 't'})
                        t.text = gt.value
                        t.tail = '\n'
                    elif gt.type in ['c']:
                        c = e.SubElement(annot, 'span', {'class':'c'})
                        c.text = gt.value
                        c.tail = '\n'
                    elif gt.type in ['w']:
                        sourceform, stage, glosslist = gt.value
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


class FileWrapper(object):
    def __init__(self, encoding='utf-8'):
        self.encoding = encoding

    def read(self, filename):
        try:
            basename, ext = os.path.splitext(filename)
        except (AttributeError):
            print "FILENAME", filename
        if ext in ['.txt']:
            self.format = 'txt'
            self._reader = TxtReader(filename)
        elif ext in ['.html', '.htm']:
            self.format = 'html'
            self._reader = HtmlReader(filename)
        self.metadata, self.para = self._reader.data()
        if self._reader.isdummy:
            self.parsed = False
            self.glosses = self.para
        else:
            self.parsed = True
            self.glosses = self._reader.glosses

    def write(self, filename, result=None, metadata=None, parsed=None):
        if result is None:
            result = self.glosses
        if metadata is None:
            metadata = self.metadata
        if parsed is None:
            parsed = self.parsed
        if parsed:
            HtmlWriter((metadata, result), filename, self.encoding).write()
        else:
            SimpleHtmlWriter((metadata, result), filename, self.encoding).write()


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
                sfm = r'\mm ' + ':'.join([gloss.form or '', '/'.join(gloss.ps or ()), gloss.gloss or '']) + os.linesep
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
        self.sha.update(repr((key,value)))
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
    def __init__(self):
        self._data = defaultdict(list)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        for (ps, gs), formlist in self._data.iteritems():
            psset = tuple(ps.split('/'))
            for form in formlist:
                yield Gloss(form, psset, gs, ())

    def __getitem__(self, gloss):
        form, ps, gs, ms = gloss
        lookup = []
        if gs:
            lookup.append((form, (ps, gs)))
        if ms:
            stems = [m for m in ms if 'mrph' not in m.ps]
            if len(stems) == 1:
                g = stems[0]
                lookup.append((g.form, (g.ps, g.gloss)))
        for f, lkp in lookup:
            try:
                variants = self._data[lkp]
                for varlist in variants:
                    if f in varlist:
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
                 variants=False, polisemy=False):

        self._dict = DabaDict()
        self._variants = VariantsDict()
        self._polisemy = defaultdict(ddlist)
        self.line = 0
        lemmalist = []
        key = None
        ps = ()
        ge = ''

        def parsemm(v):
            try:
                f, p, g = v.split(':')
                if p:
                    ps = tuple(p.split('/'))
                else:
                    ps = ()
                return Gloss(f, ps, g, ())
            except (ValueError):
                print "Error line:", str(self.line), unicode(v).encode('utf-8')

        def normalize(value): 
            return normalizeText(value.translate({ord(u'.'):None,ord(u'-'):None}).lower())

        def make_item(value):
            return [normalize(value), Gloss(form=value,ps=(),gloss="",morphemes=())]

        def push_items(primarykey, lemmalist):
            for key, lx in lemmalist:
                self._dict[key] = lx
                detonedkey = detone(key)
                if not detonedkey == key:
                    self._dict[detonedkey] = lx

        def process_record(lemmalist):
            lemmalist = [(key, item._replace(ps=ps,gloss=ge)) for key, item in lemmalist]
            if lemmalist and not ps == ('mrph',):
                if store:
                    push_items(key, lemmalist)
                if variants and len(lemmalist) > 1:
                    self._variants.add(zip(*lemmalist)[1])

        with codecs.open(filename, 'r', encoding=encoding) as dictfile:
            for line in dictfile:
                self.line = self.line + 1
                # end of the artice/dictionary
                if not line or line.isspace():
                    process_record(lemmalist)
                    lemmalist = []
                    ps = ()
                    ge = ''
                    key = None
                    seengf = False
                    seenge = False
                elif line.startswith('\\'):
                    tag, space, value = line[1:].partition(' ')
                    value = value.strip()
                    if tag in ['lang', 'ver', 'name']:
                        self._dict.__setattr__(tag, value)
                    elif tag in ['lx', 'le', 'va', 'vc']:
                        key = normalize(value)
                        lemmalist.append(make_item(value))
                    elif tag in ['mm']:
                        lemmalist[-1][1] = lemmalist[-1][1]._replace(morphemes=lemmalist[-1][1].morphemes+(parsemm(value),))
                    elif tag in ['ps'] and not ps:
                        if value:
                            ps = tuple(value.split('/'))
                        else:
                            ps = ()
                    elif tag in ['gf'] and not seengf:
                        ge = value
                        seengf = True
                    elif tag in ['ge'] and not seenge:
                        if not seengf:
                            ge = value
                            seenge = True
                    elif tag in ['gv']:
                        if polisemy:
                            self._polisemy[key][ge].append(value)
                            dk = detone(key)
                            if not dk == key:
                                self._polisemy[dk][ge].append(value)
            else:
                process_record(lemmalist)

            if not self._dict.attributed():
                print r"Dictionary does not contain obligatory \lang, \name or \ver fields.\
                        Please specify them and try to load again."
                print self._dict.lang, self._dict.name, self._dict.ver
            

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
