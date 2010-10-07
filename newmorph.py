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
        pattern = Gloss()
        pattern.ps = gloss.ps
        pattern.gloss = gloss.gloss
        return [dgloss for dgloss in gdict[gloss.form] if dgloss.matches(pattern)]
    except KeyError:
        return []

unfold = lambda l: [j for i in l for j in i]
unknown = lambda g: not bool(g.gloss)
parsed = lambda g: len([i for i in g if g.gloss]) == len(g)

def f_add(func, parses):
    '(Gloss -> [Gloss]), [Gloss] -> [Gloss]' 
    return parses.extend(unfold(filter(None, map(func, parses))))

def f_apply(func, parses):
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

class Parser(object):
    def __init__(self, dictionary, grammar):
        'Dictionary, Grammar, str -> Parser'
        self.dictionary = dictionary
        self.grammar = grammar
        self.funcdict = {
                'add': f_add, 
                'apply': f_apply, 
                'parallel': parallel, 
                'sequential': sequential, 
                'parsed': parsed, 
                'lookup': self.lookup, 
                'parse': self.parse
                }

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
            if step[0] == 'return':
                filtered = filter(self.funcdict[step[1]], parsedword)
                if filtered:
                    return (stage, parsedword)
            else:
                funclist = []
                for f in step[1]:
                    try:
                        funclist.append(self.funcdict[f])
                    except KeyError:
                        funclist.append(self.grammar.patterns[f])
                funclist.append(parsedword)
                stage = step[0]
                print parsedword
                parsedword = funclist[0](*funclist[1:])
        return parsedword

    def disambiguate(sent):
        # TODO: STUB
        for step in self.grammar.plan['sentence']:
            pass
                
    def process(self, tokens):
        '[[word]] -> [[(stage, [Gloss])]]'
        for sent in tokens:
             return self.disambiguate([self.lemmatize(word) for word in sent])
