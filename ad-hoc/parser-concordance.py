#!/usr/bin/python
# -*- encoding: utf-8 -*-

from bamana import test,wl
from nltk.text import ConcordanceIndex
from orthograph import convertw
from morphology import lemmatize, dict_disambiguate, print_gloss
import re

ci = ConcordanceIndex(test.words(), key=lambda s:s.lower())
types = list(set([s.lower() for s in set(test.words())]))
types.sort()

for word in types:
    if not re.search(r'[0-9.,;:!?]', word):
        ci.print_concordance(word, lines=15)
        print 
        nw = convertw(word)
        nwl = [w for w in nw if w in wl]
        if nwl:
            formlist = nwl
        else:
            formlist = nw
        for form in formlist:
            gl = dict_disambiguate(lemmatize(form, wl))
            glstr = [print_gloss(g) for g in gl]
            for gs in glstr:
                print "    ", gs.encode('utf-8')
        print


