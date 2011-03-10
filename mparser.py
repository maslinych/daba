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
import optparse 
import sys
import cPickle
import funcparserlib.lexer 
import xml.etree.cElementTree as e
from dictparser import DictParser
import formats


class Tokenizer(object):
    def tokenize(self, string):
        'unicode -> Sequence(Token)'
        specs = [
                ('Comment', (r'<c>.*?</c>',)),
                ('Tag', (r'<.*?>',)),
                ('NL', (r'[\r\n]+',)),
                ('Space', (r'\s+',re.UNICODE)),
                ('Punct', (r'([:;,]+)',re.UNICODE)),
                ('SentPunct', (r'([.!?]+|[)"])',re.UNICODE)),
                ('Cardinal', (r'\d+',re.UNICODE)),
                ('Word', (r"\w+([-]\w+)*[']?",re.UNICODE)),
                ('Nonword', (r'\W', re.UNICODE)),
                ]
        useless = ['NL', 'Space']
        tok = funcparserlib.lexer.make_tokenizer(specs)
        return [x for x in tok(string) if x.type not in useless]

    def split_sentences(self, para):
        sent = re.compile(r'(([^?!.]|\.\.+)+([?!.]+(\s*[)"])?|$))', re.U)
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
                    self.dictionary[key].extend(value)

    def refresh(self):
        self.dictionary = {}
        for (ids, dic) in self.dictlist.itervalues():
            self.update(dic)
        
    def add(self, dictfile):
        with open(dictfile) as f:
            dp = DictParser(f)
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

class Processor(object):
    def __init__(self, dictloader, grammarloader, script='new', encoding='utf-8'):
        self.dictloader = dictloader
        self.script = script
        self.encoding = encoding
        self.grammar = grammarloader.grammar
        self.update()

    def update(self):
        self.parser = newmorph.Parser(self.dictloader.dictionary, self.grammar)

    def read_file(self, filename):
        basename, ext = os.path.splitext(filename)
        if ext in ['.txt']:
            self.metadata, self.txt = formats.TxtReader(filename).data()
        elif ext in ['.html', '.htm']:
            self.metadata, self.txt = formats.HtmlReader(filename).data()

    def parse(self):
        self.parsed = (self.metadata,[])
        for para in self.txt:
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
                        if self.script == 'old':
                            #TODO: finish it!
                            wlist = orthography.convertw(token.value)
                            converts = [self.parser.lemmatize(w.lower()) for w in wlist]
                            successfull = [x[1] for x in filter(lambda s:s[0]>=0, converts)] or [c[1] for c in converts]
                            glosslist = []
                            for gl in successfull:
                                glosslist.extend(gl)
                        else:
                            stage, glosslist = self.parser.lemmatize(token.value.lower())

                        # suggest proper name variant for capitalized words (not in sentence-initial position
                        if token.value.istitle() and prevtoken not in [None, 'SentPunct'] and 'n.prop' not in set([]).union(*[g.ps for g in glosslist]):
                            propn = Gloss(token.value, set(['n.prop']), token.value, ())
                            glosslist.insert(0, propn)

                        annot.append(('w', (token.value, stage, glosslist)))

                    prevtoken = token.type
            self.parsed[1].append(par)
        return self.parsed

    def write(self, filename):
        formats.HtmlWriter(self.parsed, filename, self.encoding).write()

                
def main():
    usage = "%prog [options] <infile> <outfile>"
    oparser = optparse.OptionParser(usage)
    oparser.add_option("-s", "--script", metavar="script", help="Type of script (old, new)", default="new")
    oparser.add_option("-d", "--dictionary", action="append", help="Toolbox dictionary file (may be added multiple times)")
    #TODO: implement options
    (options, args) = oparser.parse_args()
    if len(args) != 2:
        oparser.error("incorrect number of arguments, should be 2: <infile> <outfile>")
    else:
        # setup parser
        infile = args[0]
        outfile = args[1]
        dl = DictLoader()
        gr = GrammarLoader()
        if options.dictionary:
            for dicfile in options.dictionary:
                dl.add(dicfile)
        pp = Processor(dl, gr, script=options.script)
        pp.read_file(infile)
        pp.parse()
        pp.write(outfile)
        exit(0)

if __name__ == '__main__':
    main()

