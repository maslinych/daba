#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import bamana
import re

c = {}

for entry in bamana.lexicon.findall('record'):
    try:
        ge = entry.find('ge').text
    except AttributeError:
        ge = ""
    lx = entry.find('lx').text
    lxlen = len(re.split(r'[.-]', lx))
    for va in entry.findall('va'):
        if len(re.split(r'[.-]', va.text)) != lxlen:
            c.setdefault((lx, ge), []).append(va.text)

for (lx, ge), vas in c.iteritems():
    print(u'{0} ‘{1}’ : {2}'.format(lx, ge, u', '.join(vas)))

