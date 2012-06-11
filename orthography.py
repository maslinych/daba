#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import unicodedata
import funcparserlib.lexer

## various utility functions (may be moved elsewhere later)
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

