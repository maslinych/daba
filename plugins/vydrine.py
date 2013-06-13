#!/usr/bin/python
# -*- coding: utf8 -*-

from . import OrthographyConverter
import os,sys
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from daba.orthography import Syllabify, ACUTE, GRAVIS, HACEK


class VydrineTonesConverter(OrthographyConverter):
    def __init__(self):
        self.title = 'vydrine'
        self.desc = "Convert Vydrine's tonal orthography into corbama standard"

    def convert(self, word):
        syllabic = orthography.Syllabify(word)
        replaced = []
        for i, tone in enumerate(syllabic.tones):
            if tone == HACEK:
                if i == len(syllabic)-1 or (i < len(syllabic)-1 and not syllabic.tone(i+1) == ACUTE):
                    syllabic.set_tone(i, GRAVIS)
                    replaced.append(i)
            elif tone == ACUTE:
                if i > 0 and i-1 not in replaced:
                    syllabic.set_tone(i, '')
                    replaced.append(i)
        if replaced:
            return [syllabic.form()]
        else:
            return [word]

