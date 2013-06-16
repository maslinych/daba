#!/usr/bin/python
# -*- coding: utf8 -*-

from . import OrthographyConverter, TonesConverter
import os,sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from daba.orthography import Syllabify, ACUTE, GRAVIS, HACEK
from collections import defaultdict


class VydrineTonesConverter(OrthographyConverter):
    def __init__(self):
        self.title = 'vydrine'
        self.desc = "Convert Vydrine's tonal orthography into corbama standard"

    def convert(self, word):
        converter = TonesConverter(word, debug=False)
        if converter.syllabify():

            for i, tone in enumerate(converter.syllabic.tones()):
            
                if tone == HACEK:
                    if i == len(converter.syllabic)-1 or (i < len(converter.syllabic)-1 and not converter.syllabic.tone(i+1) == ACUTE):
                        converter.toreplace[i].append(GRAVIS)

                elif tone == ACUTE:
                    if i > 0 and i-1 not in converter.toreplace:
                        converter.toreplace[i].append('')

        return converter.convert()
