#!/usr/bin/python
from bamana import test,wordlist,propernames
from orthograph import *

wl = set(wordlist.words())
pn = set(propernames.words())

indict = set()
inproper = set()
notindict = set()

for w in test.words():
    res = convertw(w)
    wordindict = False
    for r in res:
        word = detone(r)
        if not orth_compliant(word):
            break
        if word in wl:
            indict.add(word)
            wordindict =True
        if word in pn:
            inproper.add(word)
            wordindict = True
    else:
        if not wordindict:
            print " ".join(res).encode('utf-8')
#            notindict.add(tuple(res))


#for i in notindict:
#    for s in i:
#        print s.encode('utf-8'),
#    print
