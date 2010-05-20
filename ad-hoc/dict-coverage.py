#!/usr/bin/python
# -*- encoding: utf-8 -*-
from __future__ import division
from bamana import test,wordlist,propernames
from orthograph import *

wl = set(wordlist.words())
pn = set(propernames.words())

indict = set()
inproper = set()
notindict = set()
all = set(test.words())

for w in all:
    res = convertw(w)
    wordindict = False
    for r in res:
        word = detone(r)
        #all.add(word)
        if not orth_compliant(word):
            break
        if word in wl:
            indict.add(w)
            wordindict =True
        if word in pn:
            inproper.add(w)
            wordindict = True
    else:
        if not wordindict:
            notindict.add(w)


print 'Покрытие словарей:\nБайоль: {0:.2f}\nСобственные: {1:.2f}\nНет в словарях: {2:.2f}'.format(len(indict)/len(all),len(inproper)/len(all),len(notindict)/len(all))

print 'Объем:\nТекст: {0}\nНайденных у Байоля: {1}\nНайденных в собственных: {2}\nНе найденных: {3}'.format(len(all),len(indict),len(inproper),len(notindict))
