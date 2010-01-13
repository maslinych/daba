#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) Kirill Maslinsky <kirill@altlinux.org>
#
# Mande orthography normalization utilities
#
# This file is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#

# Orthography normalizing algorithm:
# 1. leave diacritic on first vowel
# 2. if diacritic on first vowel is missing, add acute
# 3. remove diacritics on all sucessive vowels
# 4. add acute on standalone n (or .n. as a part of composite)

import re
import unicodedata as u

class Tonograph:
    """
    Class handling tonal diacritics transformation into required orthography.
    """
    def __init__(self):
        # some static definitions
        self.dia = u'\u030c\u0300\u0301\u0302'
        self.vowel = u'aeoiuɔɛ'
        self.acute = u'\u0301'
        # prepare regexps
        self.syllable = re.compile(r'\w*?[' + self.vowel + r'][' + self.dia + r']?(?:n(?![' + self.vowel +']))?', re.I | re.U )
        self.no_dia = re.compile(r'([' + self.vowel + r'])(?![' + self.dia + r'])', re.U | re.I)
        self.n_syllabic = re.compile(r'^(n)$', re.I)
        self.word_sep = re.compile(r'((?:\w|[' + self.dia + '])+)', re.U)
        
    def words(self, line):
        """
        Returns list of words and non-word (punctuation, whitespace etc.) spans.
        """
        return re.split(self.word_sep, line, re.U | re.I)

    def syllabify_word(self, word):
        """
        Accepts a single word, returns list of syllables or given word in a case
        when given string could not be parsed as a regular word.
        """
        word_syllables = self.syllable.findall(word)
        if word_syllables:
            return [s for s in word_syllables]
        else:
            return [word]
        
    def syllables(self, line):
        """
        Returns list of words splitted in syllables as list of lists.
        """
        return [self.syllabify_word(w) for w in self.words(line)]

    def normalize_word(self, word):
        """
        Convert from Bailleuil to our tonal orthographic convention.
        Expects unicode string representing a single word, 
        returns converted NFC-normalized unicode string.

        This type of conversion is lossy (i.e. original form cannot be
        reproduced given the conversion result alone).
        """
        try:
            head, tail = word[0], word[1:]
        except IndexError:
            head = word[0]
            tail = []

        result = []
        result.append(self.n_syllabic.sub(r'\1' + self.acute, self.no_dia.sub(r'\1' + self.acute, head)))
        if tail:
            for s in tail:
                result.append(self.n_syllabic.sub(r'\1' + self.acute, re.sub(r'[' + self.dia + ']', '', s)))
        return u.normalize('NFC', ''.join(result))

    def normalize(self, line):
        """
        Returns tone-normalized NFC unicode string.
        """
        return ''.join(self.normalize_word(w) for w in self.syllables(line))

def main():
    import sys, codecs
    input = codecs.open(sys.argv[1], encoding='utf-8')
    output = codecs.open(sys.argv[2], 'w', encoding='utf-8')

    t = Tonograph()
    for line in input:
        print '|'.join(['-'.join(w).encode('utf-8') for w in t.syllables(line)])
        print t.normalize(line).encode('utf-8')

if __name__ == "__main__":
    main()
