#!/usr/bin/python
#-*- coding: utf-8 -*-

import sys
import cPickle
import unicodedata
import hashlib
from ntgloss import Gloss
from orthography import detone
from pytrie import StringTrie as trie
from collections import namedtuple

class DictParser(object):
    def __init__(self, fileobj):

        def parsemm(v):
            f, p, g = v.split(':')
            return Gloss(f, set(p.split('/')), g, ())

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
        ps = ''
        ge = ''

        for line in fileobj:
            sha.update(line)
            if not line or line.isspace():
                if tlist and ps is not set(['mrph']):
                    push_items(findict, tlist, ps, ge)
                tlist = []
                ps = ''
                ge = ''
                key = None

            elif line.startswith('\\'):
                tag, space, value = line.decode('utf-8')[1:].partition(' ')
                value = value.strip()
                if tag in ['lang', 'ver', 'name']:
                        ids[tag] = value
                if tag in ['lx', 'le', 'va', 'vc']:
                    key = unicodedata.normalize('NFC', value.translate({ord(u'.'):None,ord(u'-'):None}).lower())
                    tlist.append([key, Gloss(form=value,ps=set([]),gloss="",morphemes=())])
                if tag in ['mm']:
                    tlist[-1][1] = tlist[-1][1]._replace(morphemes=tlist[-1][1].morphemes+(parsemm(value),))
                if tag in ['ps'] and not ps:
                    ps = set(value.split('/'))
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


if __name__ == "__main__":
    with open(sys.argv[1]) as i:
        dictobj = DictParser(i).values()
    with open(sys.argv[2], 'wb') as o:
        cPickle.dump(dictobj, o)
