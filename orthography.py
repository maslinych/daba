#!/usr/bin/python
# -*- coding: utf-8 -*-

import unicodedata

## various utility functions (may be moved elsewhere later)
def multiply_list(amblist):
    # given list of lists, returns list of all possible concatenations
    # taking a single element from each list
    def multiply_list_aux(l, amblist):
        if len(amblist)>0:
            m = [ l[k]+[amblist[0][i]] for k in range(len(l)) for i in range(len(amblist[0]))]
            return multiply_list_aux(m, amblist[1:])
        else:
            return l
    return multiply_list_aux([[]], amblist)

def detone(string):
    # remove all tonemarking from string
    return "".join([c for c in unicodedata.normalize('NFD', string) if not unicodedata.category(c) == 'Mn'])

def lookup_word(lexicon, word):
    # lookup word in a lexicon (list of words)
    # returns True if word is found, False otherwise
    if detone(word) in lexicon:
        return 1
    else:
        return 0

conversion_table = {u'è':[u'ɛ'], u'ò':[u'ɔ'], u'èe':[u'ɛɛ'], u'òo':[u'ɔɔ'], u'ng':[u'ng',u'ŋ'], u'ny':[u'ny',u'ɲ']}

from nltk.tokenize import RegexpTokenizer

def graphemes_old(word):
    # split word into maximal length graphemes (old orthography)
    # !!HACK: converts word to lowercase!!
    return RegexpTokenizer(r'èe|òo|ny|ng|.').tokenize(word.lower())

def convertg(grapheme):
    # convert a single grapheme into a list of corresponding graphemes in new orthography
    try:
        return conversion_table[grapheme]
    except KeyError:
        return [grapheme]

def convertw(word):
    # given single word in old orthography returns 
    # list of all possible translations to new orthography
    graphemes = [convertg(g) for g in graphemes_old(word)]
    return [''.join(w) for w in multiply_list(graphemes)]
        
def orth_compliant(word):
    # check word for compliance with orthographic rules
    if word.startswith(u'ny'):
        return 0
    else:
        return 1


def disambiguate_word(variants):
    # given list of variants tries to filter out unlikely ones
    def add (x,y): return x+y

    for f in [orth_compliant, lookup_word]:
        if len([v for v in variants if v]) > 1:
            tests = [f(w) for w in variants]
            sum = reduce(add, tests)
            if sum != 0 and sum != len(variants):
                for t in range(len(tests)):
                    if tests[t]==0:
                        variants[t] == []
    return [v for v in variants if v]

def fromold(word):
    result = convertw(word)
    if len(result) == 1:
        return result
    else:
        return disambiguate_word(result)

#tokens = (oldtonew(w).lower() for w in testcorpus.words())

