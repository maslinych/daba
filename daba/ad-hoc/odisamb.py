#!/usr/bin/env python3
from bamana import test,wordlist,propernames
from orthography import *

wl = set(wordlist.words())
pn = set(propernames.words())

for w in test.words():
    res = convertw(w)
    if len(res) > 1:
        for r in res:
            if not orth_compliant(r):
                res.remove(r)
                break
            if detone(r) in wl:
                print("DICT:", )
            elif detone(r) in pn:
                print("PROPER:",)
            else:
                print("NOTDICT:", )
            print(r.encode('utf-8'),)
        else:
            print()
    
