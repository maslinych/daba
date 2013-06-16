#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import operator
from ntgloss import Gloss, CompactGloss, emptyGloss, Pattern, Dictionary
from orthography import detone

def nullgloss(word):
    'str -> Gloss'
    return Gloss(word, set([]), '', ())

def lookup_gloss(gloss,gdict):
    'Gloss, Dictionary -> tuple(Gloss)'
    lookup_form = None
    try:
        if gloss.form in gdict:
            lookup_form = gloss.form
        else:
            bare = detone(gloss.form)
            if not gloss.form == bare and bare in gdict:
                lookup_form = bare
        if lookup_form:
            pattern = emptyGloss._replace(ps=gloss.ps, gloss=gloss.gloss)
            return tuple([dgloss for dgloss in gdict[lookup_form] if dgloss.matches(pattern)])
        else:
            return ()
    except (KeyError,AttributeError):
        if gloss.form in gdict:
            print 'PP', gloss.form, gdict[gloss.form]
        else:
            print 'PN', gloss.form
        return ()

def parse_composite(form, gdict, numparts):
    'Str, Dictionary, Int -> [[Str]]'
    def parse_composite_aux(form, gdict, num, result):
        if not num:
            if form:
                return []
            else:
                return result
        else:
            prefixes = [p for p in gdict.iter_prefixes(form)][::-1]
            if not prefixes:
                return []
            else:
                out = []
                for pref in prefixes:
                    parsed = parse_composite_aux(form[len(pref):], gdict, num-1, result+[pref])
                    if parsed:
                        if isinstance(parsed[0], list):
                            for i in parsed:
                                out.append(i)
                        else:
                            out.append(parsed)
                return out

    return [r for r in parse_composite_aux(form, gdict, numparts, []) if r]


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
            applied = func(p[0], gl[0]) 
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

def firstmatch(func, patterns):
    '(Gloss, Pattern -> Maybe(Gloss) -> (Gloss -> Maybe([Gloss]))'
    def seq(p, gl):
        '(Pattern, Gloss -> Maybe(Gloss)), [Pattern], Gloss -> Gloss'
        if not p:
            return None
        else:
            applied = func(p[0], gl[0]) 
            if applied:
                return applied
            else:
                return seq(p[1:], gl)

    return lambda gloss: seq(patterns, [gloss])

class Parser(object):
    def __init__(self, dictionary, grammar):
        'Dictionary, Grammar, str -> Parser'
        self.dictionary = dictionary
        self.funcdict = {
                'add': f_add, 
                'apply': f_apply, 
                'parallel': parallel, 
                'sequential': sequential, 
                'firstmatch': firstmatch, 
                'parsed': parsed, 
                'lookup': self.lookup, 
                'parse': self.parse,
                'decompose': self.decompose
                }
        self.processing = []
        if grammar is None:
            self.processing.append((0, f_apply(self.lookup), ('apply', 'lookup')))
        else:
            self.grammar = grammar
            for step in self.grammar.plan['token']:
                if step[0] == 'return':
                    self.processing.append((step[0], lambda l: filter(self.funcdict[step[1]], l), step[1]))
                else:
                    funclist = []
                    for f in step[1]:
                        try:
                            funclist.append(self.funcdict[f])
                        except KeyError:
                            funclist.append(self.grammar.patterns[f])
                    self.processing.append((step[0], funclist[0](*funclist[1:]), step[1]))

    def lookup(self, lemma, make_lemma=False):
        'Gloss -> Maybe([Gloss])'
        result = None
        if parsed(lemma):
            return (lemma,)
        else:
            if lemma.morphemes:
                new = CompactGloss(*lemma)
                for i,g in enumerate(lemma.morphemes):
                    if not parsed(g):
                        dictlist = lookup_gloss(g, self.dictionary)
                        if dictlist:
                            new = new._replace(morphemes = tuple([dictlist if j==i else m for j,m in enumerate(new.morphemes)]))
                result = []
                # annotate base form with gloss derived from morpheme glosses
                for ngloss in new.glosslist:
                    glosses = [m.gloss for m in ngloss.morphemes]
                    if make_lemma and all(glosses):
                        commongloss = u'-'.join(glosses)
                    else:
                        commongloss = ''
                    stemps = [m.ps for m in ngloss.morphemes if 'mrph' not in m.ps]
                    if len(stemps) == 1:
                        try:
                            commonps = lemma.psunion(stemps[0])
                        except (ValueError):
                            commonps = lemma.ps
                    else:
                        commonps = lemma.ps
                    result.append(ngloss._replace(gloss = commongloss, ps = commonps))
            else:
                result = lookup_gloss(lemma, self.dictionary)
            return result

    def parse(self, pattern, gloss, joinchar='-'):
        'Pattern, Gloss, str="-" -> Maybe([Gloss])'
        # performs formal parsing only, does not lookup words in dict
        result = pattern.apply(gloss)
        if result:
            return [result]
        else:
            return None

    def decompose(self, pattern, gloss):
        'Pattern, Gloss -> Maybe([Gloss])'
        try:
            parts = len(pattern.select.morphemes)
        except (TypeError):
            #FIXME: morphemes=None case. Print some error message?
            pass
        result = []
        if  parts < 2:
            return self.parse(pattern, gloss)
        else:
            if gloss.morphemes:
                #FIXME: use only first non-glossed morpheme as possible stem
                stemgloss, stempos = [(m,pos) for pos,m in enumerate(gloss.morphemes) if not m.gloss][0]
            else:
                stemgloss = gloss
                stempos = -1
            if stemgloss.psmatch(pattern.select):
                stem = stemgloss.form

                decomp = [[emptyGloss._replace(form=f) for f in fl] for fl in parse_composite(stem, self.dictionary, parts)]
                if decomp:
                    newmorphemes = [tuple(m.union(p) for m,p in zip(gl, pattern.select.morphemes)) for gl in decomp]
                    for morphlist in newmorphemes:
                        if all(morphlist):
                            if stempos < 0:
                                newgloss = gloss._replace(morphemes=morphlist)
                            else:
                                mlist = list(gloss.morphemes)
                                mlist[stempos:stempos+1] = list(morphlist)
                                newgloss = gloss._replace(morphemes=tuple(mlist))
                            result.extend(filter(operator.truth, [pattern.apply(g) for g in self.lookup(newgloss) if parsed(g)]))
                    return result or None
        return None


    def lemmatize(self,word, debug=False):
        'word -> (stage, [Gloss])'
        stage = -1
        parsedword = [nullgloss(word)]
        for step, stageparser, stagestr in self.processing:
            if step == 'return':
                filtered = stageparser(parsedword)
                if filtered:
                    return (stage, filtered)
            else:
                newparsed = stageparser(parsedword)
                #FIXME: debug statement
                if not newparsed == parsedword:
                    stage = step
                    parsedword = newparsed
                if debug:
                    print stagestr
                    print stage, '\n'.join(unicode(p) for p in newparsed)
        return (stage, parsedword)

    def disambiguate(sent):
        # TODO: STUB
        for step in self.grammar.plan['sentence']:
            pass
                
    def process(self, tokens):
        '[[word]] -> [[(stage, [Gloss])]]'
        for sent in tokens:
             return self.disambiguate([self.lemmatize(word) for word in sent])
