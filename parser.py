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


class Tokenizer(object):
    def tokenize(self, string):
        'unicode -> Sequence(Token)'
        specs = [
                ('NL', (r'[\r\n]+',)),
                ('Space', (r'\s+',re.UNICODE)),
                ('Punct', (r'([:;,]+)',re.UNICODE)),
                ('SentPunct', (r'([.!?]+|[)"])',re.UNICODE)),
                ('Cardinal', (r'\d+',re.UNICODE)),
                ('Word', (r"\w+([-]\w+)*[']?",re.UNICODE)),
                ('Nonword', (r'\W+', re.UNICODE)),
                ]
        useless = ['NL', 'Space']
        tok = funcparserlib.lexer.make_tokenizer(specs)
        return [x for x in tok(string) if x.type not in useless]

    def split_sentences(self, para):
        sent = re.compile(r'(([^?!.]|\.\.+)+([?!.]+(\s*[)"])?|$))', re.U)
        for s in re.finditer(sent, para):
            yield s.group(0) or para

class DictLoader(object):
    def __init__(self):
        self.dictlist = []
        self.dictionary = {}
        for f in os.listdir(os.getcwdu()):
            name, ext = os.path.splitext(f)
            if ext in ['.bdi']:
                try: 
                    with open(f) as bdi:
                        d = cPickle.load(bdi)
                    assert isinstance(d, dict)
                    self.dictionary.update(d)
                    self.dictlist.append(f)
                except (cPickle.UnpicklingError, ImportError, AssertionError):
                    #FIXME: raise an exception with error message
                    print "Invalid binary dictionary file:", f.encode('utf-8')

class GrammarLoader(object):
    def __init__(self):
        self.gramlist = []
        self.grammar = None
        root = os.getcwdu()
        for f in os.listdir(root):
            name, ext = os.path.splitext(f)
            if ext in ['.bgr']:
                try:
                    with open(f) as gram:
                        g = cPickle.load(gram)
                    assert isinstance(g, grammar.Grammar)
                    self.gramlist.append(f)
                    self.grammar = g
                except (cPickle.UnpicklingError, ImportError, AssertionError):
                    #FIXME: raise an exception with error message
                    print "Invalid binary grammar file:", f


class Processor(object):
    def __init__(self, dictionary, grammar, script='new', encoding='utf-8'):
        self.parser = newmorph.Parser(dictionary, grammar)
        self.script = script
        self.encoding = encoding
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

    def read_file(self, filename):
        basename, ext = os.path.splitext(filename)
        if ext in ['.txt']:
            with open(filename) as f:
                self.txt = re.split(r'[\r\n]+', f.read().decode(self.encoding))
            root = e.Element('html')
            head = e.SubElement(root, 'head')
            meta = e.SubElement(head, 'meta', {'http-equiv': 'Content-Type', 'content': 'text/html; charset={0}'.format(self.encoding)})
            body = e.SubElement(root, 'body')
            self.xml = root
        elif ext in ['.html', '.xml', '.xhtml']:
            tree = e.ElementTree()
            self.xml = tree.parse(filename)
            head = self.xml.find('head')
            body = self.xml.find('body')
            self.txt = [i.text or '\n'.join([j.text for j in i.findall('span') if j.key('class') == 'sent']) for i in self.xml.findall('body/p')]
        self.body = body
        style = e.SubElement(head, 'style', {'type': 'text/css'})
        style.text = self.stylesheet

    def parse(self):
        self.body.clear()
        for para in self.txt:
            par = e.Element('p')
            for sent in Tokenizer().split_sentences(para):
                st = e.SubElement(par, 'span', {'class': 'sent'})
                st.text = sent.strip('\r\n')
                st.tail = '\n'
                annot = e.SubElement(st, 'span', {'class':'annot'})
                annot.tail = '\n'
                prevtoken = None
                for token in Tokenizer().tokenize(sent):
                    if token.type in ['Punct', 'SentPunct', 'Nonword']:
                        c = e.SubElement(annot, 'span', {'class':'c'})
                        c.text = token.value
                        c.tail = '\n'
                    elif token.type in ['Cardinal']:
                        gloss = Gloss(token.value, set(['num']), 'CARDINAL', ())
                        n = gloss.html()
                        n.text = token.value
                        n.tail = '\n'
                        annot.append(n)
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

                        variant = False
                        for gloss in glosslist:
                            if not variant:
                                w = gloss.html()
                                w.tail = '\n'
                                variant=True
                            else:
                                #NB: SIDE EFFECT!
                                w.append(gloss.html(variant=True))
                                w.tail = '\n'
                        # suggest proper name variant for capitalized words (not in sentence-initial position
                        if token.value.istitle() and prevtoken not in [None, 'SentPunct'] and 'n.prop' not in set([]).union(*[g.ps for g in glosslist]):
                            propn = Gloss(token.value, set(['n.prop']), token.value, ())
                            w.append(propn.html(variant=True))
                        annot.append(w)
                        annot.tail = '\n'
                    prevtoken = token.type
            self.body.append(par)
        return self.xml

    def html(self):
        return self.xml

    def write(self, filename):
        e.ElementTree(self.xml).write(filename, self.encoding)
        self.xml = None
                
def main():
    usage = "%prog [options] <infile> <outfile>"
    oparser = optparse.OptionParser(usage)
    oparser.add_option("-s", "--script", metavar="script", help="Type of script (old, new)", default="new")
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
        pp = Processor(dl.dictionary, gr.grammar, script=options.script)
        pp.read_file(infile)
        pp.parse()
        pp.write(outfile)
        exit(0)

if __name__ == '__main__':
    main()

