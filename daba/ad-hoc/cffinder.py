#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
from bamana import lexicon

for e in lexicon.findall('record'):
    try:
        cf = e.find('cf').text
        lx = e.find('lx').text
        if cf:
            print(lx, '->', cf)
    except AttributeError:
        pass
