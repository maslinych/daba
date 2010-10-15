#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import copy
from objects import Gloss, CompactGloss, Pattern, Dictionary

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

def f_add(func, *args):
    '(Gloss -> Maybe([Gloss])) -> ([Gloss] -> [Gloss])' 
    if args:
        f = func(*args)
    else:
        f = func
    return lambda parses: parses + unfold(filter(None, map(f, parses)))

def f_apply(func, *args):
    '(Gloss -> Maybe([Gloss])) -> ([Gloss] -> [Gloss])'
    if args:
        f = func(*args)
    else:
        f = func
    return lambda parses: unfold([f(p) or [p] for p in parses])

#def f_filter(func, *args):

def parallel(func, patterns):
    '(Gloss, Pattern -> Maybe(Gloss)) -> (Gloss -> Maybe([Gloss]))'
    return lambda gloss: unfold(filter(None, [func(p, gloss) for p in patterns]))
    
def sequential(func, patterns):
    '(Gloss, Pattern -> Maybe(Gloss) -> (Gloss -> Maybe([Gloss]))'
    def seq(p, gl, match=False):
        '(Pattern, Gloss -> Maybe(Gloss)), [Pattern], Gloss -> Gloss'
        if not p:
            if match:
                return gl
            else:
                return None
        else:
            # FIXME: use copy as workaround for side-effect operation of Pattern.apply()
            applied = func(p[0], copy.deepcopy(gl[0])) 
            if applied:
                # FIXME: here we assume func always returns list of len==1
                if match:
                    return seq(p[1:], applied + gl, match=True)
                else:
                    return seq(p[1:], applied, match=True)
            else:
                return seq(p[1:], gl, match)

    # TODO: how to process homonimous affixes? (maybe need to return list of results from single form)
    return lambda gloss: seq(patterns, [gloss])

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
        'Gloss -> Maybe([Gloss])'
        result = None
        if parsed(lemma):
            return [lemma]
        else:
            if lemma.morphemes:
                new = CompactGloss(base=lemma)
                for i,g in enumerate(lemma.morphemes):
                    if not parsed(g):
                        dictlist = lookup_gloss(g, self.dictionary)
                        if dictlist:
                            new.morphemes[i] = dictlist
                result = new.to_glosslist()
                # TODO: annotate base form with gloss derived from morpheme glosses
            else:
                result = lookup_gloss(lemma, self.dictionary)
            return result

    def parse(self, pattern, gloss, joinchar='-'):
        'Pattern, Gloss, str -> Maybe([Gloss])'
        # performs formal parsing only, does not lookup words in dict
        result = pattern.apply(gloss)
        if result:
            return [result]
        else:
            return None

    def lemmatize(self,word, debug=False):
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
                stageparser = funclist[0](*funclist[1:])
                newparsed = stageparser(parsedword)
                #FIXME: debug statement
                if debug:
                    print funclist
                    print stage, '\n'.join(' '.join([unicode(p),repr(type(p.morphemes))]) for p in newparsed),
                    print 
                if not newparsed == parsedword:
                    stage = step[0]
                    parsedword = newparsed
        return (-1, parsedword)

    def disambiguate(sent):
        # TODO: STUB
        for step in self.grammar.plan['sentence']:
            pass
                
    def process(self, tokens):
        '[[word]] -> [[(stage, [Gloss])]]'
        for sent in tokens:
             return self.disambiguate([self.lemmatize(word) for word in sent])
