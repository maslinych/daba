#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import unicodedata
import funcparserlib.lexer
from collections import namedtuple, MutableSequence

# Orthographic constants
HACEK = u'\u030c'
ACUTE = u'\u0301'
GRAVIS = u'\u0300'

# Main classes for syllabification
Syllable = namedtuple('Syllable', 'raw consonant vowel tone vowel2 tone2')

class TonalWord(MutableSequence):
    def __init__(self, word):
        nword = unicodedata.normalize('NFKD', word)        
        syllable = re.compile(r'((.*?)(?P<v>[auieoɛɔ])([\u030c\u0300\u0301\u0302])?((?P=v)?)([\u030c\u0300\u0301\u0302])?)')
        self._syllables = [Syllable(*s) for s in syllable.findall(word)]

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
        return [self.tone(s) for s in self]

    def base(self, index):
        syl = self[index]
        return syl.consonant + syl.vowel + syl.vowel2

    def detone(self):
        return u''.join([self.base(s) for s in self])

    def syllable(self, index):
        return u''.join(self[index][1:])

    def form(self):
        return u''.join([self.syllable(s) for s in self])

    def set_tone(self, index, tone):
        self[index] = self[index]._replace(tone=tone)


## various utility functions (may be moved elsewhere later)
def orth_compliant(word):
    # check word for compliance with orthographic rules
    if word.startswith(u'ny'):
        return 0
    else:
        return 1

def detone(string):
    # remove all tonemarking from string
    return "".join([c for c in unicodedata.normalize('NFD', string) if not unicodedata.category(c) == 'Mn'])

