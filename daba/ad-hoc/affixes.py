#!/usr/bin/python
# -*- encoding: utf-8 -*-

import sys
import morphology as m

for line in sys.stdin:
    word = line.strip('\n').decode('utf-8')
    derivatives = m.recursive_parse([m.strtolemma(word)], m.derivation_order, m.affixes)
    for lemma in derivatives:
        affixlist = lemma[1][1]
        if affixlist:
            affixes, glosses = zip(*affixlist)
            print u'{2} {1} {0}'.format(word, '-'.join(affixes), '-'.join(glosses))
            

