#!/usr/bin/env python3
from bamana import bailleul
from xml.etree.ElementTree import ElementTree

lexicon = ElementTree(bailleul.xml('bailleul.txt'))

tagset = [u'adj', u'adv', u'conj', u'cop', u'dtm', u'intj', u'n', u'nr', u'num', u'onomat', u'pers', u'pm', u'pm', u'pp', u'prep', u'prn', u'prt', u'ptcp', u'v', u'vq', u'mrph', u'expr']

for entry in lexicon.findall('record'):
    ps = [p.text for p in entry.findall('ps')]
    lx = entry.find('lx').text
    if len(ps) < 1:
        print(u'{0:18} {1:17} '.format(lx, u"PS TAG MISSING!"))
    elif len(ps) > 1:
        print(u'{0:18} {1:17} '.format(lx, u"MULTIPLE PS TAGS:"),)
        for t in ps:
            print(t,)
        print
    elif len([f for f in ps[0].split(u'/') if f not in tagset]) > 0:
        print(u'{0:18} {1:17} '.format(lx, u"NOT IN TAGSET:"),)
        print(ps[0])

