#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import copy
from objects import Gloss, Pattern, Dictionary

def nullgloss(word):
    'str -> Gloss'
    return Gloss(word + '::')

def lookup_gloss(gloss,gdict):
    'Gloss, Dictionary -> [Gloss]'
    try:
        pattern = Gloss()
        pattern.ps = gloss.ps
        pattern.gloss = gloss.gloss
        return [dgloss for dgloss in gdict[gloss.form] if dgloss.matches(pattern)]
    except KeyError:
        return []

unfold = lambda l: [j for i in l for j in i]
unknown = lambda g: not bool(g.gloss)
def parsed(g):
    if g.morphemes:
        return len([m for m in g.morphemes if m.gloss]) == len(g.morphemes)
    else:
        return bool(g.gloss)

def f_add(func, parses):
    '(Gloss -> [Gloss]), [Gloss] -> [Gloss]' 
    result = (unfold(filter(None, map(func, parses))))
    parses.extend(result)
    return parses

def f_apply(func, parses):
    '(Gloss -> [Gloss]), [Gloss] -> [Gloss]' 
    return unfold(filter(None, [func(p) or [p] for p in parses]))

def parallel(func, patterns, parses):
    '(Gloss, [Pattern] -> Gloss), [Gloss] -> [Gloss]'
    return unfold([filter(None, [func(p, g) for p in patterns]) or [g] for g in parses])
    
def sequential(func, patterns, parses):
    '(Gloss, [Pattern] -> Gloss), [Pattern], [Gloss] -> [Gloss]'
    def seq(f, p, g):
        '(Pattern, Gloss -> (Gloss | None)), [Pattern], Gloss -> Gloss'
        if not p:
            return g
        else:
            applied = func(p[0], g) 
            if applied:
                return seq(f, p[1:], applied)
            else:
                return seq(f, p[1:], g)

    # TODO: how to process homonimous affixes? (maybe need to return list of results from single form)
    return [seq(func, patterns, g) for g in parses]


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
        if parsed(lemma):
            return [lemma]
        else:
            for i,g in enumerate(lemma):
                if not parsed(g):
                    for dictword in lookup_gloss(g, self.dictionary):
                        new = copy.deepcopy(lemma)
                        new[i] = dictword
                        result.append(new)
                        # TODO: annotate base form with gloss derived from morpheme glosses
            return result

    def parse(self, pattern, gloss, joinchar='-'):
        'Pattern, Gloss, str -> Gloss'
        # performs formal parsing only, does not lookup words in dict
        return pattern.apply(gloss)

    def lemmatize(self,word):
        'word -> (stage, [Gloss])'
        stage = -1
        parsedword = [nullgloss(word)]
        for step in self.grammar.plan['token']:
            if step[0] == 'return':
                filtered = filter(self.funcdict[step[1]], parsedword)
                if filtered:
                    return (stage, filtered)
            else:
                funclist = []
                for f in step[1]:
                    try:
                        funclist.append(self.funcdict[f])
                    except KeyError:
                        funclist.append(self.grammar.patterns[f])
                funclist.append(parsedword)
                newparsed = funclist[0](*funclist[1:])
                if not newparsed == parsedword:
                    stage = step[0]
                    parsedword = newparsed
        return (stage, parsedword)

    def disambiguate(sent):
        # TODO: STUB
        for step in self.grammar.plan['sentence']:
            pass
                
    def process(self, tokens):
        '[[word]] -> [[(stage, [Gloss])]]'
        for sent in tokens:
             return self.disambiguate([self.lemmatize(word) for word in sent])
