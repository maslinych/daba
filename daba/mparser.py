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
import grammar
from ntgloss import Gloss, emptyGloss
import os
import argparse
import sys
import cPickle
import funcparserlib.lexer
import formats
from plugins import OrthographyConverter
import pkg_resources
import plugins.tokenizer


class Tokenizer(object):
    def tokenize(self, string):
        'unicode -> Sequence(Token)'
        tok = funcparserlib.lexer.make_tokenizer(plugins.tokenizer.specs)
        return tok(string)

    def split_sentences(self, toklist):
        senttoks = []
        bordertypes = ['SentPunct', 'Par']
        border = False
        for n, tok in enumerate(toklist):
            senttoks.append(tok)
            if tok.type in bordertypes:
                border = True
            elif tok.type not in bordertypes and border:
                border = False
                yield senttoks[:-1]
                senttoks = [tok]
            else:
                border = False
        else:
            yield senttoks


class ChainDict(object):
    def __init__(self, *maps):
        self._maps = dict((dic.hash, dic) for dic in maps)

    @property
    def ids(self):
        return self._maps.viewkeys()

    @property
    def dictlist(self):
        return self._maps.viewvalues()

    def __len__(self):
        return sum([len(dic) for dic in self.dictlist])

    def __iter__(self):
        for dic in self.dictlist:
            for key in dic:
                yield key

    def __contains__(self, key):
        for dic in self.dictlist:
            if key in dic:
                return True
        return False

    def __getitem__(self, key):
        result = []
        for mapping in self.dictlist:
            try:
                result.extend(mapping[key])
            except KeyError:
                pass
        if result:
            return result
        else:
            raise KeyError(key)

    def iter_prefixes(self, key):
        result = set()
        for dic in self.dictlist:
            for prefix in dic.iter_prefixes(key):
                result.add(prefix)
        return result

    def iteritems(self):
        result = []
        keysseen = []
        for mapping in self.dictlist:
            for key in mapping:
                if key not in keysseen:
                    for lookup in self.dictlist:
                        try:
                            result.extend(lookup[key])
                        except (KeyError):
                            pass
                    yield (key, result)
                    keysseen.append(key)
                    result = []

    def get_dict(self, sha):
        return self._maps[sha]

    def add(self, dic):
        self._maps[dic.hash] = dic

    def remove(self, sha):
        del self._maps[sha]

    def replace(self, sha, dic):
        self._maps[sha] = dic


class DictLoader(object):
    """ Object holding info about dictionaries state.
    """
    def __init__(self, runtimedir='./run', verbose=False):
        self.runtimedir = runtimedir
        self.dictionary = ChainDict()
        self.verbose = verbose
        if not os.path.exists(self.runtimedir):
            os.mkdir(self.runtimedir)
        else:
            for f in os.listdir(self.runtimedir):
                name, ext = os.path.splitext(f)
                if ext in ['.bdi']:
                    with open(os.path.join(self.runtimedir, f)) as bdi:
                        dic = cPickle.load(bdi)
                        assert isinstance(dic, formats.DabaDict)
                        self.load(dic)

    def filepath(self, dic):
        return os.path.join(self.runtimedir, os.path.extsep.join(['-'.join([dic.lang, dic.name, dic.hash]), 'bdi']))

    def load(self, dic):
        if self.verbose:
            sys.stderr.write(u'LOADED DICT {}\n'.format(dic).encode('utf-8'))
        self.dictionary.add(dic)

    def addfile(self, dictfile):
        dic = formats.DictReader(dictfile).get()
        if not dic.hash in self.dictionary.ids:
            self.add(dic)
            return dic.hash

    def add(self, dic):
        for d in self.dictionary.dictlist:
            if (dic.lang, dic.name) == (d.lang, d.name):
                if not (dic.ver, dic.hash) == (d.ver, d.hash):
                    break
                else:
                    # don't save dic if we already have identical one
                    return (dic.lang, dic.name)
        else:
            self.save(dic)
            return dic.hash
        self.remove(d.hash)
        self.save(dic)
        return dic.hash

    def remove(self, dicid):
        for d in self.dictionary.dictlist:
            if d.hash == dicid:
                dic = d
                break
        if self.verbose:
            sys.stderr.write(u'REMOVED DICT {}\n'.format(dic).encode('utf-8'))
        self.dictionary.remove(dic.hash)
        os.unlink(self.filepath(dic))

    def save(self, dic):
        if self.verbose:
            sys.stderr.write(u'DICT saved {}\n'.format(dic).encode('utf-8'))
        self.load(dic)
        with open(self.filepath(dic), 'wb') as o:
            cPickle.dump(dic, o)


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
    def __init__(self, dictloader=None, grammarloader=None, converters=None, detone=False, nolemmas=False):
        self.converters = converters
        self.detone = detone
        if nolemmas:
            class Noparser(object):
                def lemmatize(self, wform):
                    return ('-1', [emptyGloss._replace(form=wform)])
            self.parser = Noparser()
        else:
            self.dictloader = dictloader
            self.grammar = grammarloader.grammar
            self.parser = newmorph.Parser(self.dictloader.dictionary, self.grammar, detone=self.detone)
        
    def parse(self, txt):
        self.parsed = []
        tkz = Tokenizer()
        for para in txt:
            par = []
            for sent in tkz.split_sentences(tkz.tokenize(para)):
                st = (''.join(t.value for t in sent), [])
                par.append(st)
                annot = st[1]
                prevtoken = False
                for token in sent:
                    if token.type in ['Comment', 'Tag']:
                        annot.append(formats.GlossToken((token.type, token.value)))
                    elif token.type in ['Punct', 'SentPunct', 'Nonword']:
                        annot.append(formats.GlossToken(('c', token.value)))
                    elif token.type in ['Cardinal']:
                        gloss = Gloss(token.value, ('num',), 'CARDINAL', ())
                        annot.append(formats.GlossToken(('w', (token.value, 'tokenizer', [gloss]))))
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
                        if token.value.istitle() and prevtoken and 'n.prop' not in set([]).union(*[g.ps for g in glosslist]):
                            propn = Gloss(token.value, ('n.prop',), token.value, ())
                            glosslist.append(propn)

                        annot.append(formats.GlossToken(('w', (token.value, unicode(stage), glosslist))))
                        prevtoken = True

            self.parsed.append(par)
        return self.parsed


def load_plugins():
    plugins = {
        plugin.name: plugin.load()
        for plugin
        in pkg_resources.iter_entry_points('daba.plugins')
    }
    return plugins


def parse_file(infile, outfile, pp, args):
    print 'Processing', infile
    io = formats.FileWrapper()
    io.read(infile)
    io.write(outfile, pp.parse(io.para), parsed=True, format=args.format)
    print 'Finished', outfile


def main():
    
    plugins = load_plugins()

    aparser = argparse.ArgumentParser(description='Daba suite. Command line morphological parser.')
    aparser.add_argument('-i', '--infile', help='Input file (.txt or .html)', default="sys.stdin")
    aparser.add_argument('-o', '--outfile', help='Output file', default="sys.stdout")
    aparser.add_argument('-s', '--script', action='append', choices=plugins.keys(), default=None, help='Perform orthographic conversion operations (defined in plugins). Conversions will be applied in the order they appear on command line.')
    aparser.add_argument("-d", "--dictionary", action="append", help="Toolbox dictionary file (may be added multiple times)")
    aparser.add_argument("-g", "--grammar", help="Grammar specification file")
    aparser.add_argument("-n", "--noparse", action='store_true', help="Do not parse, only process resources")
    aparser.add_argument("-N", "--nolemmas", action='store_true', help="Do not lemmatize, only tokenize input")
    aparser.add_argument("-l", "--list", help="Read input filenames list from file")
    aparser.add_argument("-t", "--detone", action='store_true', help="Ignore tones in dictionary lookups")
    aparser.add_argument("-f", "--format", action='store', choices=formats.FileWrapper().output_formats, default="html", help="Output file format")
    aparser.add_argument("-v", "--verbose", action='store_true', help="Print info messages on loaded dictionaries")
    args = aparser.parse_args()

    if args.nolemmas:
        pp = Processor(converters=args.script, detone=args.detone, nolemmas=True)
    else:
        dl = DictLoader(verbose=args.verbose)
        gr = GrammarLoader()
        if args.dictionary:
            for dicfile in args.dictionary:
                dl.addfile(dicfile)
        if args.grammar:
            gr.load(args.grammar)
    if not args.noparse:
        if not args.nolemmas:
            pp = Processor(dictloader=dl, grammarloader=gr, converters=args.script, detone=args.detone)
        if args.list:
            with open(args.list) as filelist:
                for line in filelist:
                    infile = os.path.normpath(line.decode('utf-8').strip())
                    if os.path.exists(infile):
                        outfile = os.path.splitext(infile)[0] + '.pars.html'
                        parse_file(infile, outfile, pp, args)
        else:
            parse_file(args.infile, args.outfile, pp, args)
    exit(0)


if __name__ == '__main__':
    main()

