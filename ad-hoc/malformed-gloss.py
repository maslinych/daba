#!/usr/bin/python
# -*- encoding: utf-8 -*-

import bamana

c = {}

for entry in bamana.lexicon.findall('record'):
    try:
        ge = entry.find('ge').text
    except AttributeError:
        ge = ""
    if u' ' in ge:
        print u'{0} ‘{1}’'.format(entry.find('lx').text, ge)

