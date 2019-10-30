#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from bamana import wl,test
from nltk import FreqDist
from orthograph import convertw, detone

words = []
for i in test.words():
    words.extend(convertw(detone(i)))
fd = FreqDist(words)

for w, lems in wl.items():
    if len(lems) > 1:
        pslist = reduce(lambda x,y: x.union(y), [lem[1] for lem in lems])
        if len(pslist) > 1:
        #if len(pslist) == 1: # polysemy case
            print fd[detone(w)], w,
            for l in lems:
                print '|', '/'.join(l[1]), u"‘" + l[2] + u"’",
            print

