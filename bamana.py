#!/usr/bin/python
# -*- ecnoding: utf-8 -*-
from nltk.corpus.reader import PlaintextCorpusReader, ToolboxCorpusReader
from nltk.corpus.util import LazyCorpusLoader
from nltk.tokenize import RegexpTokenizer
from xml.etree.ElementTree import ElementTree
from orthograph import detone

orthographic_word = RegexpTokenizer(r"\w+([-]\w+)*[']?")

test = LazyCorpusLoader(
        'bamana/test', PlaintextCorpusReader, r'source.txt', word_tokenizer=orthographic_word, encoding='utf-8')

wordlist = LazyCorpusLoader(
        'bamana/wordlist', PlaintextCorpusReader, r'bailleul.clean.wordlist', word_tokenizer=orthographic_word, encoding='utf-8')

properlist = LazyCorpusLoader(
        'bamana/propernames', PlaintextCorpusReader, r'.*\.clean\.wordlist', word_tokenizer=orthographic_word, encoding='utf-8')

propernames = LazyCorpusLoader(
        'bamana/propernames', ToolboxCorpusReader, '.*\.txt', encoding='utf-8')

bailleul = LazyCorpusLoader(
        'bamana/bailleul', ToolboxCorpusReader, r'bailleul.txt', encoding='utf-8')

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
        ps = set(entry.find('ps').text.split('/'))
    except AttributeError:
        ps = set([])
    try:
        gloss = entry.find('ge').text
    except AttributeError:
        gloss = ''
    for lemma in lemmas:
        wl.setdefault(lemma.lower(), []).append((lemma,ps,gloss))
        wl.setdefault(detone(lemma.lower()), []).append((lemma,ps,gloss))
