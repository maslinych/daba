#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from __future__ import division
import sys
import digrams
import unicodedata
import codecs

d = codecs.open(sys.argv[1], 'r', encoding='utf-8')

familiar_ngrams = set([])

for i in d:
    familiar_ngrams.add(i.strip('\n'))

d.close()

for line in sys.stdin:
    word = unicodedata.normalize('NFC', unicode(line.strip('\n').decode('utf-8')))
    c = 0
    max = ((len(word)+2)*2)-3
    positive = []
    negative = []
    for n in map(lambda x: x+1, range(3))[1:]:
        for ngram in digrams.ngrams(word, n):
            if ngram in familiar_ngrams:
                c = c+1
                positive.append(ngram)
            else:
                negative.append(ngram)
    print(u'{1:.2f}\t{0}\t{2} | {3}'.format(word, c/max, ';'.join(positive), ' '.join(negative)))
