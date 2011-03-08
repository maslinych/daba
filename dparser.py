#!/usr/bin/python
#-*- coding: utf-8 -*-

import sys
import cPickle
import unicodedata
from ntgloss import Gloss
from orthography import detone

findict = {}

def parsemm(v):
    f, p, g = v.split(':')
    return Gloss(f, p.split('/'), g, ())

def push_items(d, l, ps=frozenset([]), ge=''):
    for k, i in l:
        lx = i._replace(ps=set([ps]),gloss=ge)
        d.setdefault(k,[]).append(lx)
        detoned = detone(k)
        if not detoned == k:
            d.setdefault(detoned,[]).append(lx)

tlist = []
key = None
ps = ''
ge = None
with open(sys.argv[1], 'rb') as f:
    for line in f:
        if not line or line.isspace():
            if tlist and ps not in ['mrph']:
                push_items(findict, tlist, ps, ge)
            tlist = []
            ps = ''
            ge = None
            key = None

        elif line.startswith('\\'):
            tag, space, value = line.decode('utf-8')[1:].partition(' ')
            value = value.strip()
            if tag in ['lx', 'le', 'va', 'vc']:
                key = unicodedata.normalize('NFC', value.translate({ord(u'.'):None,ord(u'-'):None}).lower())
                tlist.append([key, Gloss(form=value,ps=set([]),gloss="",morphemes=())])
            if tag in ['mm']:
                tlist[-1][1] = tlist[-1][1]._replace(morphemes=tlist[-1][1].morphemes+(parsemm(value),))
            if tag in ['ps'] and not ps:
                ps = value
            if tag in ['ge'] and not ge:
                ge = value

with open(sys.argv[2], 'wb') as o:
    cPickle.dump(findict, o)
