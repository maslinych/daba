#!/usr/bin/python

from bamana import bailleul
from xml.etree.ElementTree import ElementTree
import re

lexicon = ElementTree(bailleul.xml('bailleul.txt'))
wl = {}

for entry in lexicon.findall('record'):
    lemma = entry.find('lx').text
    try:
        ps = entry.find('ps').text
    except AttributeError:
        ps = 'UNK'
    try:
        gloss = entry.find('ge').text
    except AttributeError:
        gloss = 'UNKNOWN'
    wl.setdefault(lemma, []).append((lemma,ps,gloss))
    wl.setdefault(detone(lemma), []).append((lemma,ps,gloss))

def stem(word):
    'wordform -> (lemma, affix)'
    stemmed = re.match(r'^(\w+)(w|ra|la|na)$', word, re.U)
    if stemmed:
        return stemmed.groups()
    else:
        return (word, '')

def lemmatize(word):
    'wordform -> [(lemma,ps,gloss)]'
    'str -> [(str, [str], [str])]'
    'wordform -> [(lemma, [prefix], [affix])]'
    try:
        return wl[word]
    except KeyError:
        try:
            lem, aff = stem(word)
            if aff:
                return wl[lem]
        except KeyError:
            return [(word, 'UNK','UNKNOWN')]

