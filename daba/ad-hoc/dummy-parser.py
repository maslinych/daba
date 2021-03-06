#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from orthograph import convertw
from morphology import lemmatize, dict_disambiguate, print_gloss
from bamana import wl, test
import re

sents = re.split(r'([^!?:;.\n\t]+[!?:;.]+)', test.raw())
sent = [s for s in sents if s]
ww = [re.split(r'[- .,;!?"]', s) for s in sent if s]
words = [[w for w in wlist if w] for wlist in ww]

for sentence in words:
    i = 0
    print(' '.join(sentence).strip('\n\t'))
    for word in sentence:
        nw = convertw(word)
        nwl = [w for w in nw if w in wl]
        if nwl:
            formlist = nwl
        else:
            formlist = nw

        print('/'.join(formlist), "\t(",)
        for j in range(len(sentence)):
            if j == i:
                print(sentence[j].upper() + " ",)
            else:
                print(sentence[j] + " ",)
        print(")")
        for form in formlist:
            gl = dict_disambiguate(lemmatize(form, wl))
            glstr = [print_gloss(g) for g in gl]
            for gs in glstr:
                print("    ", gs)
        i += 1
        print
    print

