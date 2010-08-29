#!/usr/bin/python
# -*- encoding: utf-8 -*-

from bamana import bailleul
from orthograph import detone
import re
import xml.etree.ElementTree as e

def sfec(result, morphlist):
    'Search For Embedded Composites'
    '[morph] -> [(morph)]'
    newlist = []
    if not result:
        if len(morphlist) > 2:
            result.append(tuple(morphlist[:-1]))
            newlist = sfec(result, morphlist)
        else:
            newlist.extend([(m,) for m in morphlist])
    elif len(result[-1]) > 2:
        result.append(result[-1][:-1])
        newlist = sfec(result, morphlist)
    else:
        newlist = result
        newlist.extend([(m,) for m in morphlist])
    return newlist

elist = bailleul.entries('bailleul.txt')
etree = e.ElementTree(bailleul.xml('bailleul.txt'))

morphdict = {}

for entry in etree.findall('record'):
    lx = entry.findtext('lx', default='')
    ge = entry.findtext('ge', default='')
    ps = entry.findtext('ps')
    lems = [lx]
    for va in entry.findall('va'):
        lems.append(va.text)
    for v in lems:
        lemma = v.strip(u'-')
        morphdict.setdefault(tuple(re.split(r'[.-]', v.strip(u'-').lower())), []).append((lemma,ps,ge))
        if v != detone(v):
            morphdict.setdefault(tuple(re.split(r'[.-]', detone(v.strip(u'-').lower()))), []).append((lemma,ps,ge))
    
for (lemma,fields) in elist:
    forms = [(-1, lemma)]
    forms.extend([(index,value) for index, (tag,value) in enumerate(fields) if tag == 'va'])
    shift = 1
    for i, form in forms:
        morphs = re.split(r'[.-]+', form)
        # prepare >=2 morph sequences for lookup 
        mlist = sfec([], morphs)
        if len(mlist) > 1 and () not in mlist:
            for morph in mlist:
                try:
                    for gloss in morphdict[morph]:
                        fields.insert(i+shift, (r'mm', ':'.join(gloss)))
                        shift = shift+1
                except KeyError:
                    if len(morph) == 1:
                        fields.insert(i+shift, (r'mm', u':'.join([morph[0], u'?', u'????'])))
                        shift = shift+1

    print u'\\lx {0}'.format(lemma)
    for tag,value in fields:
        print u'\\{0} {1}'.format(tag, value)
    print

