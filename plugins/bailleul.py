#!/usr/bin/python
# -*- coding: utf8 -*-

from . import OrthographyConverter
import os,sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from daba.orthography import Syllabify, ACUTE, GRAVIS, HACEK


class BailleulTonesConverter(OrthographyConverter):
    def __init__(self):
        self.title = 'bailleul'
        self.desc = "Convert Bailleul's tonal orthography into corbama standard"

    def convert(self, word, debug=False):
        try:
            syllabic = Syllabify(word)
        except (ValueError) as e:
            if debug:
                print unicode(e).encode('utf-8')
            return [word]
        replaced = []
        toreplace = []
        for i, tone in enumerate(syllabic.tones()):
            if tone == HACEK:
                syllabic.set_tone(i, GRAVIS)
                replaced.append(i)
            if i == 0 and not tone:
                syllabic.set_tone(i, ACUTE)
                replaced.append(i)
            if tone == ACUTE and syllabic.tone(i-1) == ACUTE:
                toreplace.append(i)
                
        for j in toreplace:
            syllabic.set_tone(j, '')
            replaced.append(j)

        if debug:
            print u' '.join([word, '->', syllabic.form()]).encode('utf-8')
        if replaced:
            return [syllabic.form()]
        else:
            return [word]

