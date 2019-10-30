#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import unicodedata
from collections import namedtuple, MutableSequence

# Orthographic constants
HACEK = u'\u030c'
ACUTE = u'\u0301'
GRAVIS = u'\u0300'

# Main classes for syllabification
class Syllable(namedtuple('Syllable', 'raw consonant vowel1 tone1 vowel2 tone2 nasal')):
    __slots__ = ()
    @property
    def tone(self):
        return self.tone1 + self.tone2

    @property
    def vowel(self):
        return self.vowel1 + self.vowel2


class Syllabify(MutableSequence):
    def __init__(self, word):
        nword = unicodedata.normalize('NFKD', word)        
        self._syllables = []
        index = 0
        syllable = re.compile(ur"""
                (                                           # raw: whole syllable group
                    ([^auieoɛɔƐƆ\u030c\u0300\u0301\u0302]*)   # consonant: optional initiale
                    (?P<v>[auieoɛɔwnŋɲƐƆ'])                      # vowel: syllable core, obligatory
                    ([\u030c\u0300\u0301\u0302]?)           # tone: for the vowel
                    ((?P=v)?)                                # vowel2: long vowels (same vowel letter)
                    ([\u030c\u0300\u0301\u0302]?)           # tone2: possible tone marker on vowel2
                    (n?(?![auieoɛɔ\u0301]))                 # nasal: finale, not followed by vowel or tone
                )""", re.I|re.X)
        for syl in syllable.finditer(nword):
            if syl.start()-index > 0:
                raise ValueError(u"Nonconforming syllabic structure: {0}, at pos: {1}-".format(nword, nword[:index+1]))
            else:
                index = syl.end()
                try:
                    self._syllables.append(Syllable(*syl.groups()))
                except (TypeError):
                    print syl.groups()
        if index < len(nword):
            raise ValueError(u"Nonconforming syllabic structure: {0}, at pos: {1}-".format(nword, nword[:index]))

    def __len__(self):
        return len(self._syllables)

    def __getitem__(self, index):
        return self._syllables[index]

    def __setitem__(self, index, item):
        self._syllables[index] = item

    def __delitem__(self, index):
        del self._syllables[index]

    def insert(self, index, item):
        self._syllables.insert(index, item)

    def tone(self, index):
        syl = self[index]
        return syl.tone + syl.tone2

    def tones(self):
        return [self.tone(s) for s in range(len(self))]

    def base(self, index):
        syl = self[index]
        return syl.consonant + syl.vowel + syl.vowel2 + syl.nasal

    def detone(self):
        return u''.join([self.base(s) for s in self])

    def syllable(self, index):
        return u''.join(self[index][1:])

    def form(self):
        return u''.join([self.syllable(s) for s in range(len(self))])

    def set_tone(self, index, tone):
        if len(tone) == 2:
            self[index] = self[index]._replace(tone1=tone[0], tone2=tone[1])
        else:
            self[index] = self[index]._replace(tone1=tone)


## various utility functions (may be moved elsewhere later)
def orth_compliant(word):
    # check word for compliance with orthographic rules
    if word.startswith(u'ny'):
        return 0
    else:
        return 1

def detone(string):
    # remove all tonemarking from string
    return "".join([c for c in unicodedata.normalize('NFD', unicode(string)) if not unicodedata.category(c) == 'Mn'])


def tones_match(source, tonalized):
    source = unicodedata.normalize('NFD', source)
    tonalized = unicodedata.normalize('NFD', tonalized)
    for c in tonalized:
        if source:
            if unicodedata.category(c) == 'Mn':
                if unicodedata.category(source[0]) == 'Mn':
                    if not c == source[0]:
                        return False
                    else:
                        source = source[1:]
            else:
                source = source[1:]
    return True

