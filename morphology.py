#!/usr/bin/python
# -*- encoding: utf-8 -*-

from bamana import bailleul,propernames
from orthograph import detone
from syllables import syllabify
from xml.etree.ElementTree import ElementTree
import re
from operator import and_

lexicon = ElementTree(bailleul.xml('bailleul.txt'))

for file in propernames.fileids():
    for e in ElementTree(propernames.xml(file)).findall('record'):
        lexicon.getroot().append(e)

wl = {}

def normalize_bailleul(word):
    return u''.join([c for c in word if c not in u'.-'])

for entry in lexicon.findall('record'):
    lemmas = [normalize_bailleul(entry.find('lx').text)]
    lemmas.extend([normalize_bailleul(e.text) for e in entry.findall('va')])
    try:
        ps = entry.find('ps').text
    except AttributeError:
        ps = 'UNK'
    try:
        gloss = entry.find('ge').text
    except AttributeError:
        gloss = 'UNKNOWN'
    for lemma in lemmas:
        wl.setdefault(lemma.lower(), []).append((lemma,ps,gloss))
        wl.setdefault(detone(lemma.lower()), []).append((lemma,ps,gloss))

#def deaffix(word, regex, gloss):
#    '(wordform, regex, gloss) -> (stem, (affix, gloss))'
#    '([(stem, gloss)], regex, gloss) -> [(stem, gloss)]'

PROG = ([[r'n$', r'^na$'], [r'[^n]$', r'^la$']], -1, ['v'], 'PROG')
IPFV_INTR = ([[r'(^nmɲŋ|n$)', r'^na$'], [r'[rl].*[^n]$', r'^la$'], [r'.*', r'^ra$']], -1, ['v'], 'IPFV.INTR')
PL = ([[r'^w$']], -1, ['n', 'adj', 'dtm', 'prn'], 'PL')

# affix structure:
# surface (strings/syllables, position in word)
# context (re/sllables, relative position to surface)
# gloss
# stem class (pstags list)

def match_affix(syllables, affix):
    '[syllable], affix -> True | False'
    def cmp(regex, str):
        if not str:
            str = ''
        if regex:
            if not re.search(regex, str):
                return False
            else:
                return True
        else:
            return True
    return reduce(and_, map(cmp, affix[::-1], syllables[::-1]))


def stem(word):
    'wordform -> [(lemma, affix, [pstag])]'
    stemmed = []
    syls = syllabify(word)
    for v in syls:
        for affix in [PL, PROG, IPFV_INTR]:
            for a in affix[0]:
                if match_affix(v, a):
                    if affix[1] < 0:
                        lemma = ''.join(v[:affix[1]])
                        aff = ''.join(v[affix[1]:]), affix[3]
                    else:
                        lemma = ''.join(v[affix[1]:])
                        aff = ''.join(v[affix[1]:]), affix[3]
                    stemmed.append((lemma, aff, affix[2]))
    if stemmed:
        return stemmed 
    else:
        return [(word, ('',''), '')]

def lemmatize(wordform):
    'wordform -> [(lemma,ps,gloss)]'
    'str -> [(str, [str], [str])]'
    'wordform -> [(lemma, [prefix], [affix])]'
    word = wordform.lower()
    variants = []
    if word in wl: 
        variants.extend(wl[word])
    lem, aff = stem(word)
    if aff and lem in wl:
        variants.extend(wl[lem])
    if not variants:
        detoned = detone(word)
        if detoned in wl:
            variants.extend(wl[detoned])
    #    variants = [(word, 'UNK','UNKNOWN')]
    return variants
