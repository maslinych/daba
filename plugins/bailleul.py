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
       converter = TonesConverter(word, debug=True)
       if converter.syllabify():

            for i, syl in enumerate(converter.syllabic):

                if syl.tone == HACEK and not converter.syllabic[i+1].tone == ACUTE:
                    converter.toreplace[i].append(GRAVIS)

                if not syl.tone and i == 0 and not syl.vowel == "'":
                    converter.toreplace[i].append(ACUTE)

                if syl.tone and not syl.tone == HACEK and syl.tone == converter.syllabic[i-1].tone:
                    converter.toreplace[i].append('')

                if syl.tone == GRAVIS and syl.vowel2 and not syl.tone2:
                    converter.toreplace[i].append(GRAVIS + GRAVIS)

                if syl.vowel == 'w' and syl.tone == GRAVIS:
                    converter.toreplace[i].append('')
                    
       return converter.convert()

