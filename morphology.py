#!/usr/bin/python
# -*- encoding: utf-8 -*-

#from bamana import bailleul,propernames
from orthograph import detone
from syllables import syllabify
import re
from operator import and_


## AFFIXES
affixes = { 'PROG': ([[r'n$', r'^na$'], [r'[^n]$', r'^la$']], -1, 'PROG') , 
        'IPFV.INTR': ([[r'(^[nmɲŋ]|n$)', r'^na$'], [r'[rl].+[^n]$', r'^la$'], [r'.', r'^ra$']], -1, 'IPFV.INTR') ,
        'PL': ([[r'.', r'^w$']], -1, 'PL'),
        'ABSTR': ([[r'.', r'^ya$']], -1, 'ABSTR'),
        'DIM': ([[r'.', r'^nin$']], -1, 'DIM'),
        'AUG': ([[r'.', r'^ba$']], -1, 'AUG'),
        'GENT': ([[r'.', r'^ka$']], -1, 'GENT'),
        'AG.EX': ([[r'.', r'^nci$']], -1, 'AG.EX'),
        'LOC': ([[r'n$', r'na'], [r'.', r'la']], -1, 'LOC'),
        'MENT1': ([[r'.', r'^la$'], [r'.', r'^na$']], -1, 'MENT1'),
        'MENT2': ([[r'.', r'^la$', r'^ta$'], [r'.', r'^na$', r'^ta$']], -2, 'MENT2'),
        'COM': ([[r'.', r'^ma$']], -1, 'COM'),
        'RECP.PRN': ([[r'.', r'^ma$']], -1, 'RECP.PRN'),
        'PRIV': ([[r'.', r'^ntan$']], -1, 'PRIV'),
        'AG.OCC': ([[r'.', r'^ba$', r'^ga$']], -2, 'AG.OCC'),
        # HACK!
        'AG.OCC2': ([[r'.', r'^baa$']], -1, 'AG.OCC'),
        'PTCP.PRIV': ([[r'.', r'^ba$', r'^li$']], -2, 'PTCP.PRIV'),
        'RES': ([[r'n$', r'^nen$'], [r'.', r'^len$']], -1, 'RES'),
        'AG.PRM': ([[r'n$', r'^na$'], [r'.', r'^la$']], -1, 'AG.PRM'),
        'INSTR': ([[r'n$', r'^nan$'], [r'.', r'^lan$'], [r'.', r'ran']], -1, 'INSTR'),
        'NMLZ': ([[r'n$', r'^ni$'], [r'.', r'^li$']], -1, 'NMLZ'),
        'DIR': ([[r'.', r'^ma$']], -1, 'DIR'),
        'RECP1': ([[r'.', r'^ɲo$', r'^gon$']] ,-2,'RECP'),
        'RECP2': ([[r'.', r'^ɲwaa?n']], -1, 'RECP'),
        'PTCP.POT': ([[r'.', r'^ta$']], -1, 'PTCP.POT'),
        'PTCP.PROG': ([[r'.', r'^tɔ']], -1, 'PTCP.PROG'),
        'CAUS': ([[r'^(la|lá)$', r'.'], [r'^(na|ná)$', r'.']], 1, 'CAUS'),
        'SUPER': ([[r'^(ma|mà)n?$', r'.']], 1, 'SUPER'),
        'DEQU': ([[r'^ya$', r'.']], -1, 'DEQU'),
        'ADJ': ([[r'^man$', r'.']], -1, 'ADJ')
        }

## DERIVATIONAL SCHEMES
nominal_inflection = { 'pslist': set(['n', 'adj', 'dtm', 'prn']), 'ranks': {-1: ['PL']}}
verbal_inflection = { 'pslist': set(['v']) , 'ranks': {-1: ['PROG', 'IPFV.INTR']}}
nominal_derivation = { 'pslist': set(['n']), 'ranks': {-1: ['ABSTR'],
    -2: ['AUG'], -3: ['DIM'], -4: ['GENT', 'AG.EX'], -5: ['LOC', 'MENT1', 'MENT2', 'COM', 'RECP.PRN', 'PRIV']} }
adj_derivation = { 'pslist': set(['adj']), 'ranks': {-1: ['ABSTR'], -2: ['DIM', 'AUG']}}
verbal_derivation = { 'pslist': set(['v']), 'ranks': { -1: ['ABSTR'], -2: ['DIM', 'AUG'], -3: ['GENT', 'RECP.PRN', 'AG.EX'],
    -4: ['AG.OCC', 'AG.OCC2', 'PTCP.PRIV', 'RES', 'AG.PRM', 'LOC', 'MENT1', 'MENT2', 'INSTR', 'NMLZ', 'DIR', 'RECP1', 'RECP2', \
            'PTCP.POT', 'PTCP.PROG'], 
    1: ['CAUS'], 2: ['SUPER']}}
vq_derivation = {'pslist': set(['vq']), 'ranks': { -1: ['AUG', 'DIM'], -2: ['PTCP.PRIV', 'RES', 'PTCP.POT', 'PTCP.PROG', 'AG.EX'],
    -3: ['DEQU', 'ADJ']}}

parse_order = [vq_derivation, adj_derivation, verbal_derivation, nominal_derivation, verbal_inflection, nominal_inflection]

def match_affix(syllables, morpheme, direction):
    '[syllable], morpheme, cutoff_syllable -> True | False'
    def cmp(regex, str):
        if not str:
            str = ''
        if regex:
            return bool(re.search(regex, str))
        else:
            return True
    if direction < 0:
        return reduce(and_, map(cmp, morpheme[::-1], syllables[::-1]))
    else:
        return reduce(and_, map(cmp, morpheme, syllables))

def deaffix(word, affix):
    'wordform, affix -> (stem, affixlist)'
    stemmed = ()
    syls = syllabify(word)
    for v in syls:
        for allomorph in affix[0]:
            if match_affix(v, allomorph, affix[1]):
                if affix[1] < 0:
                    lemma = ''.join(v[:affix[1]])
                    aff = (), (''.join(v[affix[1]:]), affix[2])
                else:
                    lemma = ''.join(v[affix[1]:])
                    aff = (''.join(v[:affix[1]]), affix[2]), ()
                stemmed = (lemma, aff)
    if stemmed:
        return stemmed 
    else:
        return (word, ((),()))

def merge_affixlist(afflist, addition):
    'affixlist -> affixlist'
    prefix, suffix = addition
    if suffix:
        suffix = [suffix] + afflist[1]
    else:
        suffix = afflist[1]
    if prefix:
        prefix = afflist[0] + [prefix]
    else:
        prefix = afflist[0]
    return prefix, suffix

def psmatch(source, target):
    'set, set -> set'
    if not source:
        return target
    else:
        return source.intersection(target)

def parse_derivative_ranked(lemmalist, scheme, affixdict, ranklist, pslist):
    '[lemma], scheme, affixdict, ranklist, pslist -> [lemma]'
    r = ranklist[-1]
    ranklist = ranklist[:-1]
    stemmed = []
    for lemma in lemmalist:
        for affixgloss in scheme['ranks'][r]:
            stem, (prefix, suffix) = deaffix(lemma[0], affixdict[affixgloss])
            if suffix or prefix:
                stemmed = stemmed + [(stem, merge_affixlist(lemma[1], (prefix,suffix)), pslist)]
    stemmed = lemmalist + stemmed
    if ranklist:
        return parse_derivative_ranked(stemmed, scheme, affixdict, ranklist, pslist)
    else:
        return stemmed

def parse_derivative(lemma, scheme, affixdict):
    'lemma, scheme, affixdict -> [lemma]'
    'lemma:: (stem, affixlist, pslist)'
    ranks = scheme['ranks'].keys()
    ranks.sort()
    pslist = psmatch(lemma[2], scheme['pslist'])
    if pslist:
        return parse_derivative_ranked([lemma], scheme, affixdict, ranks, pslist)
    else:
        return [lemma]

def apply_scheme(lemmalist, scheme, affixdict):
    '[lemma], scheme, affixdict -> [lemma]'
    return [result for lemma in lemmalist for result in parse_derivative(lemma,scheme,affixdict) ]

def recursive_parse(lemmalist, schemelist, affixdict):
    '[lemma], schemelist, affixdict -> [lemma]'
    nextscheme = schemelist[-1]
    schemelist = schemelist[:-1]
    newlist = apply_scheme(lemmalist, nextscheme, affixdict)
    if schemelist:
        return recursive_parse(newlist, schemelist, affixdict)
    else:
        return newlist

def strtolemma(wordform):
    'wordform -> lemma'
    return (wordform, ([],[]), set([]))

def lookup_lemma(lemma, glossary):
    'lemma, glossary -> [gloss]'
    'gloss:: lemma + gloss'
    glosslist = []
    if lemma[0] in glossary:
        for gloss in glossary[lemma[0]]:
            pslist = psmatch(lemma[2], gloss[1])
            if pslist:
                glosslist.append((lemma[0], lemma[1], pslist, gloss[2]))
    if not glosslist:
        glosslist.append((lemma[0], lemma[1], lemma[2], ''))
    return glosslist

def dict_disambiguate(glosslist):
    '[gloss] -> [gloss]'
    indict = [g for g in glosslist if g[3]]
    if indict:
        return indict
    else:
        return glosslist

def lemmatize(wordform, glossary):
    'wordform, glossary -> [gloss]'
    # formal parsing
    lems = recursive_parse([strtolemma(wordform.lower())], parse_order, affixes)
    glos = [gloss for lemma in lems for gloss in lookup_lemma(lemma, glossary)]
    return dict_disambiguate(glos) 

def print_gloss(gloss):
    'gloss -> str'
    stem, (preflist, sufflist), pslist, ge = gloss
    if preflist:
        prefmorph, prefgloss = zip(*preflist)
    else:
        prefmorph, prefgloss = [], []
    if sufflist:
        suffmorph, suffgloss = zip(*sufflist)
    else:
        suffmorph, suffgloss = [], []
    form = '-'.join([i for j in [prefmorph, [stem], suffmorph] for i in j])
    glossstring = '-'.join([i for j in [prefgloss, [stem], suffgloss] for i in j])
    psstring = '/'.join(pslist)
    return u'{0} {1} {2} ‘{3}’'.format(form, glossstring, psstring, ge)

