#!/usr/bin/python
# -*- encodnig: utf-8 -*-

import unicodedata
import re
import collections

def ngrams(s, ngram=2):
    #app = ''.join(' ' for i in range(ngram-1))
    app = '_'
    word = collections.deque(unicodedata.normalize('NFC', ''.join([app, s, app])))
    while len(word) >= ngram:
        ngrami = ''.join([word[i] for i in range(ngram)])
        word.popleft()
        yield ngrami

def __main__():
    from bamana import test
    from orthograph import convertw
    ng = collections.defaultdict(int)

    for i in test.words():
        if not re.search(r'[0-9.,;:!?]', i):
            for w in convertw(i):
                for n in map(lambda x:x+1, range(3)):
                    for g in ngrams(w, ngram=n):
                        ng[g] = ng[g]+1

    for g, f in ng.iteritems():
        print u'{0} {1}'.format(g,f)
