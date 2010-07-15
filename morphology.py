#!/usr/bin/python
# -*- encoding: utf-8 -*-

#from bamana import bailleul,propernames
from orthograph import detone
from syllables import syllabify
import re
from operator import and_, truth
from itertools import combinations, product


## AFFIXES
affixes = { 'PROG': ([[r'n$', r'^na$'], [r'[^n]$', r'^la$']], -1, 'PROG') , 
        'IPFV.INTR': ([[r'(^[nmɲŋ]|n$)', r'^na$'], [r'[rl].+[^n]$', r'^la$'], [r'.', r'^ra$']], -1, 'IPFV.INTR') ,
        'PL': ([[r'.', r'^w$']], -1, 'PL'),
        'ABSTR': ([[r'.', r'^ya$']], -1, 'ABSTR'),
        'DIM': ([[r'.', r'^nin$']], -1, 'DIM'),
        'AUG': ([[r'.', r'^ba$']], -1, 'AUG'),
        'GENT': ([[r'.', r'^ka$']], -1, 'GENT'),
        'AG.EX': ([[r'.', r'^nci$']], -1, 'AG.EX'),
        'LOC': ([[r'n$', r'^na$'], [r'[^n]$', r'^la$']], -1, 'LOC'),
        'MENT1': ([[r'.', r'^la$'], [r'.', r'^na$']], -1, 'MENT1'),
        'MENT2': ([[r'.', r'^la$', r'^ta$'], [r'.', r'^na$', r'^ta$']], -2, 'MENT2'),
        'COM': ([[r'.', r'^ma$']], -1, 'COM'),
        'RECP.PRN': ([[r'.', r'^ma$']], -1, 'RECP.PRN'),
        'PRIV': ([[r'.', r'^ntan$']], -1, 'PRIV'),
        'AG.OCC': ([[r'.', r'^ba$', r'^ga$']], -2, 'AG.OCC'),
        # HACK!
        'AG.OCC2': ([[r'.', r'^baa$']], -1, 'AG.OCC'),
        'PTCP.PRIV': ([[r'.', r'^ba$', r'^li$']], -2, 'PTCP.PRIV'),
        'RES': ([[r'n$', r'^nen$'], [r'[^n]$', r'^len$']], -1, 'RES'),
        'AG.PRM': ([[r'n$', r'^na$'], [r'[^n]$', r'^la$']], -1, 'AG.PRM'),
        'INSTR': ([[r'n$', r'^nan$'], [r'[^n]$', r'^lan$'], [r'[^n]$', r'ran']], -1, 'INSTR'),
        'NMLZ': ([[r'n$', r'^ni$'], [r'[^n]$', r'^li$']], -1, 'NMLZ'),
        'DIR': ([[r'.', r'^ma$']], -1, 'DIR'),
        'RECP1': ([[r'.', r'^ɲo$', r'^gon$']] ,-2,'RECP'),
        'RECP2': ([[r'.', r'^ɲwaa?n']], -1, 'RECP'),
        'PTCP.POT': ([[r'.', r'^ta$']], -1, 'PTCP.POT'),
        'PTCP.PROG': ([[r'.', r'^tɔ']], -1, 'PTCP.PROG'),
        'CAUS': ([[r'^(la|lá)$', r'.'], [r'^(na|ná)$', r'.']], 1, 'CAUS'),
        'SUPER': ([[r'^(ma|mà)n?$', r'.']], 1, 'SUPER'),
        'DEQU': ([[r'^ya$', r'.']], -1, 'DEQU'),
        'ADJ': ([[r'^man$', r'.']], -1, 'ADJ'),
        'PRICE': ([[r'n$', r'^na$'], [r'[^n]$', r'^la$']], -1, 'PRICE')
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
inflection_order = [verbal_inflection, nominal_inflection]
derivation_order = [vq_derivation, adj_derivation, verbal_derivation, nominal_derivation]

## COMPOSITE SCHEMES
nominal_composites = {'pslist': set(['n']), 
        'templates': [ [set(['n']), set(['n'])],
            #[set(['n']), set(['v'])],
            [set(['dtm']), set(['v'])],
            [set(['n']), set(['adj'])],
            [set(['v']), set(['n'])],
            [set(['n']), set(['num'])],
            [set(['n']), set(['adj']), set(['n'])],
            [set(['n']), set(['v']), set(['n'])],
            [set(['dtm']), set(['v']), set(['n'])],
            [set(['n']), set(['pp']), set(['n'])],
            #[set(['n']), set(['pp']), set(['v'])]
            ]}

verbal_composites = {'pslist': set(['v', 'n']), 'templates': [
    [set(['n']), set(['v'])],
    [set(['n']), set(['pp']), set(['v'])]
    ]}

composite_order = [nominal_composites, verbal_composites]


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

def splitlist(list, points):
    prev = 0
    result = []
    for p in points:
        result.append(list[prev:p])
        prev = p
    result.append(list[prev:])
    return result

def splitpoints(i):
    return [p for p in combinations(range(i)[1:],1)] + \
           [p for p in combinations(range(i)[1:],2)]

def split_composite(syllables):
    '[syllables] -> [[stems]]'
    def rejoin(list):
        '[[str]] -> [str]'
        return [''.join(i) for i in list]

    return [rejoin(splitlist(syllables,p)) for p in splitpoints(len(syllables))]

def match_template(glosses, template):
    if len(glosses) == len(template):
        return reduce(and_, map(truth, map(psmatch, zip(*glosses)[2], template)))
    else:
        return False

def parse_composite(gloss, glossary):
    'gloss -> [gloss]'
    result = []
    stem, afflist, pslist, ge = gloss
    # syllabify stem
    syls = syllabify(stem)
    for scheme in composite_order:
        if psmatch(pslist, scheme['pslist']):
            for variant in syls:
                if len(variant) > 2:
                    splits = split_composite(variant)
                    for split in splits:
                        possible_gloss = product(*[lookup_lemma(strtolemma(stem), glossary) for stem in split])
                        possible_gloss = [gl for gl in possible_gloss if reduce(and_, map(truth, zip(*gl)[3]))]
                        for glosses in possible_gloss:
                            for template in scheme['templates']:
                                if match_template(glosses, template):
                                    result.append(('.'.join(zip(*glosses)[0]), afflist, psmatch(pslist,scheme['pslist']), '.'.join(zip(*glosses)[3])))

    return result

def parse_reduplicate(gloss,glossary):
    'gloss -> [gloss]'
    result = []
    if len(gloss[0]) > 0:
        middle = len(gloss[0]) // 2
        if len(gloss[0]) % 2 and gloss[0][middle] == u'-':
                fhalf = gloss[0][:middle]
                shalf = gloss[0][middle+1:]
        else:
            fhalf = gloss[0][:middle]
            shalf = gloss[0][middle:]
        if fhalf == shalf:
            glosses = lookup_lemma((fhalf,gloss[1],gloss[2]),glossary)
            for g in glosses:
                result.append((fhalf,g[1],psmatch(gloss[2],g[2]),g[3] + ' [reduplicate]'))
    return result
                    
def filter_glosslist(glosslist):
    '[gloss] -> [gloss] | []'
    return filter(lambda x: truth(x[3]), glosslist)

def lemmatize(wordform, glossary, minimal=True):
    'wordform, glossary -> (stage, [gloss])'
    # inflection parsing
    result = []
    nulllemma = strtolemma(wordform.lower())
    # dictionary lookup
    lems = recursive_parse([nulllemma], inflection_order, affixes)
    glos = [gloss for lemma in lems for gloss in lookup_lemma(lemma, glossary)]
    disambiguated = dict_disambiguate(glos) 
    # in case of unsuccessful lookup, let's go deeper
    if not filter_glosslist(disambiguated):
        # check for derivation
        derivatives = [g for lem in recursive_parse(lems, derivation_order, affixes) for g in lookup_lemma(lem, glossary)]
        if filter_glosslist(derivatives):
            stage = 1
            result.extend(filter_glosslist(derivatives))
        else:
            # check for reduplication
            reduplicates = filter(truth, [glo for r in derivatives for glo in parse_reduplicate(r,glossary)])
            if reduplicates:
                stage = 2
                result.extend(reduplicates)
            else:
                # check for composites
                composites = filter(truth, [glo for c in derivatives for glo in parse_composite(c,glossary)])
                if composites:
                    stage = 3
                    result.extend(composites)

        # last resort: provide minimum-info or null lemma
        if not result:
            stage = -1
            result = disambiguated
    # initial lookup was successful
    else:
        stage = 0
        result = disambiguated
    return (stage, result)

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

