#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import newmorph
import orthography
import grammar
from ntgloss import Gloss
import os
import re
import argparse
import sys
import cPickle
import funcparserlib.lexer 
import xml.etree.cElementTree as e
import formats
from plugins import OrthographyConverter


class Tokenizer(object):
    def tokenize(self, string):
        'unicode -> Sequence(Token)'
        specs = [
                ('Comment', (r'<c>.*?</c>',)),
                ('Tag', (r'<.*?>',)),
                ('Par', (r'(\r?\n){2,}',)),
                ('NL', (r'[\r\n]',)),
                ('Space', (r'\s+',re.UNICODE)),
                ('Punct', (r'([:;,]+)',re.UNICODE)),
                ('SentPunct', (r'([.!?]+|[)"])',re.UNICODE)),
                ('Cardinal', (r'\d+',re.UNICODE)),
                #FIXME: hardcoded acute and grave accents plus round apostrophe (shoud not split words)
                ('Word', (ur"(\w[\u0300\u0301]?)+([-](\w[\u0300\u0301]?)+)*['\u2019]?",re.UNICODE)),
                ('Nonword', (r'\W', re.UNICODE)),
                ]
        useless = ['NL', 'Space']
        tok = funcparserlib.lexer.make_tokenizer(specs)
        return [x for x in tok(string) if x.type not in useless]

    def split_sentences(self, para):
        sent = re.compile(r'(([^?!.]|\.\.+)+?([?!.]+(\s*[)"])?|(\r?\n){2,}|$))', re.U)
        for s in re.finditer(sent, para):
            yield s.group(0) or para


class DictLoader(object):
    """ Object holding info about dictionaries state.
    """
    def __init__(self, runtimedir='./run'):
        self.runtimedir = runtimedir
        self.dictlist = {}
        self.dictionary = {}
        for f in os.listdir(self.runtimedir):
            name, ext = os.path.splitext(f)
            if ext in ['.bdi']:
                with open(os.path.join(self.runtimedir, f)) as bdi:
                    sha, lang, name, ver, dic = cPickle.load(bdi)
                self.dictlist[(lang, name)] = ( (ver, sha), dic)
                self.refresh()

    def update(self, dic):
        if not self.dictionary:
            self.dictionary = dic
        else:
            for key,value in dic.iteritems():
                if key not in self.dictionary:
                    self.dictionary[key] = value
                else:
                    for gloss in value:
                        if gloss not in self.dictionary[key]:
                            self.dictionary[key].append(gloss)

    def refresh(self):
        self.dictionary = {}
        for (ids, dic) in self.dictlist.itervalues():
            self.update(dic)
        
    def add(self, dictfile):
        dp = formats.DictReader(dictfile)
        if not any(dp.values()):
            return (None, None)
        sha, lang, name, ver, dic = dp.values()
        if (lang, name) not in self.dictlist:
            self.update(dic)
        elif not self.dictlist[(lang, name)][0] == (ver, sha):
            self.remove((lang, name))
            self.refresh()
        self.dictlist[(lang, name)] = ((ver, sha), dic)
        self.save((lang, name))
        return (lang, name)

    def remove(self, dictid):
        lang, name = dictid
        ((ver, sha), dic) = self.dictlist[dictid] 
        os.unlink(os.path.join(self.runtimedir, os.path.extsep.join(['-'.join([lang, name, sha]), 'bdi'])))
        del self.dictlist[dictid]
        self.refresh()

    def save(self, dictid):
        lang, name = dictid
        ((ver, sha), dic) = self.dictlist[dictid]
        with open(os.path.join(self.runtimedir, os.path.extsep.join(['-'.join([lang, name, sha]), 'bdi'])), 'wb') as o:
            cPickle.dump((sha, lang, name, ver, dic), o)


class GrammarLoader(object):
    def __init__(self, runtimedir="./run"):
        self.runtimedir = runtimedir
        self.gramlist = []
        self.grammar = None
        root = os.getcwdu()
        for f in os.listdir(self.runtimedir):
            name, ext = os.path.splitext(f)
            if ext in ['.bgr']:
                try:
                    with open(os.path.join(self.runtimedir, f), 'rb') as gram:
                        g = cPickle.load(gram)
                    assert isinstance(g, grammar.Grammar)
                    self.gramlist = [name]
                    self.grammar = g
                except (cPickle.UnpicklingError, ImportError, AssertionError):
                    #FIXME: raise an exception with error message
                    print "Invalid binary grammar file:", f
    
    def load(self, gramfile):
        self.grammar = grammar.Grammar(gramfile)
        self.gramlist = [os.path.basename(gramfile)]
        # take basename of the gramfile as a 
        for f in os.listdir(self.runtimedir):
            name, ext= os.path.splitext(f)
            if ext in ['.bgr']:
                os.unlink(os.path.join(self.runtimedir, f))
        with open(os.path.join(self.runtimedir, os.path.extsep.join([os.path.basename(gramfile), 'bgr'])), 'wb') as o:
            cPickle.dump(self.grammar, o)


class FileWrapper(object):
    def __init__(self, encoding='utf-8'):
        self.encoding = encoding

    def read(self, filename):
        basename, ext = os.path.splitext(filename)
        if ext in ['.txt']:
            self.metadata, self.txt = formats.TxtReader(filename).data()
        elif ext in ['.html', '.htm']:
            self.metadata, self.txt = formats.HtmlReader(filename).data()

    def write(self, parsed, filename):
        formats.HtmlWriter((self.metadata, parsed), filename, self.encoding).write()


class Processor(object):
    def __init__(self, dictloader, grammarloader, converters=None):
        self.dictloader = dictloader
        self.converters = converters
        self.grammar = grammarloader.grammar
        self.parser = newmorph.Parser(self.dictloader.dictionary, self.grammar)

    def parse(self, txt):
        self.parsed = []
        for para in txt:
            par = []
            for sent in Tokenizer().split_sentences(para):
                st = (sent, [])
                par.append(st)
                annot = st[1]
                prevtoken = None
                for token in Tokenizer().tokenize(sent):
                    if token.type in ['Comment', 'Tag']:
                        annot.append((token.type, token.value))
                    elif token.type in ['Punct', 'SentPunct', 'Nonword']:
                        annot.append(('c', token.value))
                    elif token.type in ['Cardinal']:
                        gloss = Gloss(token.value, set(['num']), 'CARDINAL', ())
                        annot.append(('w', (token.value, 'tokenizer', [gloss])))
                    elif token.type in ['Word']:
                        if self.converters:
                            wlist = [token.value]
                            for plugin in self.converters:
                                converted = []
                                for w in wlist:
                                    for result in OrthographyConverter.get_plugins()[plugin].convert(w):
                                        converted.append(result)
                                wlist = converted
                            converts = [self.parser.lemmatize(w.lower()) for w in wlist]
                            successfull = [x[1] for x in filter(lambda s:s[0]>=0, converts)] or [c[1] for c in converts]
                            stage = max([c[0] for c in converts])
                            glosslist = []
                            for gl in successfull:
                                glosslist.extend(gl)
                        else:
                            stage, glosslist = self.parser.lemmatize(token.value.lower())

                        # suggest proper name variant for capitalized words (not in sentence-initial position)
                        if token.value.istitle() and prevtoken not in [None, 'SentPunct'] and 'n.prop' not in set([]).union(*[g.ps for g in glosslist]):
                            propn = Gloss(token.value, set(['n.prop']), token.value, ())
                            glosslist.insert(0, propn)

                        annot.append(('w', (token.value, unicode(stage), glosslist)))

                    prevtoken = token.type
            self.parsed.append(par)
        return self.parsed


def load_plugins():
    plugins = [x[:-3] for x in os.listdir('plugins') if x.endswith('.py') and not x.startswith('__')]
    for plugin in plugins:
        mod = __import__('.'.join(['plugins', plugin]))
                
def main():
    
    load_plugins() 

    aparser = argparse.ArgumentParser(description='Daba suite. Command line morphological parser.')
    aparser.add_argument('infile', help='Input file (.txt or .html)')
    aparser.add_argument('outfile', help='Output file')
    aparser.add_argument('-s', '--script', action='append', choices=OrthographyConverter.get_plugins().keys(), default=None, help='Perform orthographic conversion operations (defined in plugins). Conversions will be applied in the order they appear on command line.')
    aparser.add_argument("-d", "--dictionary", action="append", help="Toolbox dictionary file (may be added multiple times)")
    aparser.add_argument("-g", "--grammar", help="Grammar specification file")
    args = aparser.parse_args()
    dl = DictLoader()
    gr = GrammarLoader()
    if args.dictionary:
        for dicfile in args.dictionary:
            dl.add(dicfile)
    if args.grammar:
        gr.load(args.grammar)
    pp = Processor(dl, gr, converters=args.script)
    io = FileWrapper()
    io.read(args.infile)
    io.write(pp.parse(io.txt), args.outfile)
    exit(0)

if __name__ == '__main__':
    main()

