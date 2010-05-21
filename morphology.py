#!/usr/bin/python

from bamana import bailleul,propernames
from orthograph import detone
from xml.etree.ElementTree import ElementTree
import re

lexicon = ElementTree(bailleul.xml('bailleul.txt'))
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

for name in propernames.word():


def stem(word):
    'wordform -> (lemma, affix)'
    stemmed = re.match(r'^(\w+)(w|ra|la|na)$', word, re.U)
    if stemmed:
        return stemmed.groups()
    else:
        return (word, '')

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
