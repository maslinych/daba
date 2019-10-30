#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from morphology import wl
from syllables import syllabify
import unicodedata

for i, lx in wl.items():
    for lemma in lx:
        if 'n' in lemma[1].split('/'):
            t = u''.join(syllabify(lemma[0])[0][1:])
            for c in unicodedata.normalize('NFD', t):
                if unicodedata.category(c) == 'Mn':
                    print(lemma[0].encode('utf-8'), "\t", "‘" + lemma[2].encode('utf-8') + "’")
                    break

