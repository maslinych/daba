#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
from bamana import lexicon, normalize_bailleul
from orthograph import detone

def shorten(s):
    return normalize_bailleul(detone(s))

for e in lexicon.findall('record'):
    lx = e.find('lx').text
    for va in e.findall('va'):
        if va.text and (len(shorten(lx))-len(shorten(va.text)))>2:
            print(lx, ':', va.text)
