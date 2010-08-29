#!/usr/bin/python
# -*- encoding: utf-8 -*-

from __future__ import division
from bamana import test,wl,wl_detone
from orthograph import convertw,detone
from morphology import lemmatize, dict_disambiguate, print_gloss
from nltk import FreqDist
import re

types = list(set([s.lower() for s in set(test.words())]))
types.sort()

wlist = [convertw(w) for w in types if not re.search(r'[0-9.,;:!?]', w)]
fdist = FreqDist(tuple(convertw(w)) for w in test.words() if not re.search(r'[0-9.,;:!?]', w))

def counts(wordlist,fd):
    for word in wordlist:
            stages = -2
            length = []
            result = []
            for form in word:
                if form != detone(form):
                    stage, gl = lemmatize(form, wl)
                else:
                    stage, gl = lemmatize(form,wl_detone)
                if stages < stage:
                    stages = stage
                result.extend(gl)
            length = len(dict_disambiguate(result))
            yield (stages, length, u' '.join(word), fd[tuple(word)])

for t in counts(wlist,fdist):
    print u'{0},{1},{2},{3}'.format(*t)

