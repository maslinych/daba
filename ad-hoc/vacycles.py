#!/usr/bin/python
# -*- encoding: utf-8 -*-
from bamana import lexicon, normalize_bailleul

lxs = set([])
vas = {}
for e in lexicon.findall('record'):
    lx = e.find('lx').text
    lxs.add(normalize_bailleul(lx))
    for va in e.findall('va'):
        if va.text:
            vas[normalize_bailleul(va.text)] = (va.text, lx)

for va,pair in vas.iteritems():
    if va in lxs:
        print u'{0} -> {1}'.format(*pair)
