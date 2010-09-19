#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import copy
from objects import Gloss, Pattern, Dictionary

def nullgloss(word):
    'str -> Gloss'
    return Gloss(word + '::')

def lookup_gloss(gloss,gdict):
    try:
        return [dgloss for dgloss in gdict[gloss.form] if dgloss.psmatch(gloss)]
    except KeyError:
        return []

unfold = lambda l: [j for i in l for j in i]
unknown = lambda g: not bool(g.gloss)
parsed = lambda g: len([for i in g if g.gloss]) == len(g)

def add(func, parses):
    '(Gloss -> [Gloss]), [Gloss] -> [Gloss]' 
    return parses.extend(unfold(filter(None, map(func, parses))))

def apply(func, parses):
    '(Gloss -> [Gloss]), [Gloss] -> [Gloss]' 
    return unfold(map(func, parses)) or parses

def parallel(func, patterns, parses):
    '(Gloss, [Pattern] -> [Gloss]), [Gloss] -> [Gloss]'
    return unfold([func(p, g) for p in patterns for g in parses])
    
def sequential(func, patterns, parses):
    '(Gloss, [Pattern] -> [Gloss]), [Gloss] -> [Gloss]'
    def seq(f, p, g):
        if not p:
            return g
        else:
            func(p[0], g) or seq(f, p[1:], g)

    return unfold([seq(func, patterns, g) for g in parses])

def return_parse(func, parses):
    if all(map(func,parses)):


class Parser(object):
    def __init__(self, dictionary, grammar, orthography='new'):
        'Dictionary, Grammar, str -> Parser'
        self.dictionary = dictionary
        self.grammar = grammar
        self.orthography = orthography
        self.funcdict = {'add': add, 'apply': apply, 'parallel': parallel, 'sequential': sequential, 'parsed': parsed}


    def lookup(self, lemma):
        'Gloss -> [Gloss]'
        result = []
        for i,g in enumerate(lemma):
            if unknown(g):
                dictwords = [w for w in lookup_gloss(g, self.dictionary)]
                if dictwords:
                    newresult = []
                    for res in result:
                        for dictword in dictwords:
                            new = copy.deepcopy(res)
                            new[i] = dictword
                            newresult.append(new)
                    result = newresult
                    # TODO: annotate base form with gloss derived from morpheme glosses
        return result

    def parse(self, patterns, gloss, joinchar='-'):
        'Pattern, Gloss, str -> [Gloss]'
        # performs formal parsing only, does not lookup words in dict
        return pattern.apply(gloss) or []

    def lemmatize(self,word):
        'word -> (stage, [Gloss])'
        stage = None
        parsedword = [nullgloss(word)]
        for step in self.grammar.plan['token']:
            if step[1] == 'return':
                if all(map(self.funcdict[step[2]], parsedword)):
                    return (stage, parsedword)
            else:
                stage = step[0]
                funclist = [self.funcdict[i] for i in step[1:]]
                funclist.append(parsedword)
                parsedword = self.funcdict[funclist[0]](*funclist[1:])
        return parsedword

    def disambiguate:
        # TODO: STUB
        for step in self.grammar.plan['sentence']:
            pass
                
    def process(self, tokens):
        '[[word]] -> [[(stage, [Gloss])]]'
        for sent in tokens:
             return self.disambiguate([self.lemmatize(word) for word in sent])
