#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import bamana

c = {}

for entry in bamana.lexicon.findall('record'):
    try:
        ge = entry.find('ge').text
    except AttributeError:
        ge = ""
    lx = entry.find('lx').text
    c.setdefault(ge, []).append(lx)

for gloss, lemmas in c.iteritems():
    if len(lemmas) > 1:
        print u'{0}: {1}'.format(gloss, u', '.join(lemmas))

