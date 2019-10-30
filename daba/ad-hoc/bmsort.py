#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import sys
import icu
import codecs

ioencoding='utf-8'

lines = sys.stdin.readlines()
lines = [l.decode(ioencoding).strip('\n') for l in lines]
lines.sort(cmp=icu.Collator.createInstance(icu.Locale('bm_ML')).compare)
for l in lines:
    print l.encode(ioencoding)

