#!/usr/bin/python
# -*- coding: utf8 -*-

from . import OrthographyConverter, TonesConverter
import os,sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from daba.orthography import Syllabify, ACUTE, GRAVIS, HACEK
from collections import defaultdict

class BailleulTonesConverter(OrthographyConverter):
    def __init__(self):
        self.title = 'bailleul'
        self.desc = "Convert Bailleul's tonal orthography into corbama standard"

    def convert(self, word):
       converter = TonesConverter(word, debug=False)
       if converter.syllabify():

            for i, syl in enumerate(converter.syllabic):

                if syl.tone == HACEK and ( len(converter.syllabic) == i+1 or not converter.syllabic[i+1].tone == ACUTE ):
                        converter.toreplace[i].append(GRAVIS)

                if i == 0 and not syl.tone and not syl.vowel == "'":
                    converter.toreplace[i].append(ACUTE)

                if i > 0 and syl.tone in [ACUTE, GRAVIS] and syl.tone == converter.syllabic[i-1].tone:
                    converter.toreplace[i].append('')

                if syl.vowel == 'w' and syl.tone == GRAVIS:
                    converter.toreplace[i].append('')
                    
       return converter.convert()

