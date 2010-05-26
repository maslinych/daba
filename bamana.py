#!/usr/bin/python
# -*- ecnoding: utf-8 -*-
from nltk.corpus.reader import PlaintextCorpusReader, ToolboxCorpusReader
from nltk.corpus.util import LazyCorpusLoader
from nltk.tokenize import RegexpTokenizer

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
