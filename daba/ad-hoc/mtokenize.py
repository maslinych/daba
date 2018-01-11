#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from daba.mparser import Tokenizer

debug = True

tkz = Tokenizer()

with open(sys.argv[1]) as f:
    txt = f.read().decode("utf-8")
    for sent in tkz.split_sentences(tkz.tokenize(txt)):
        if debug:
            print ""
            print "SENT"
        for token in sent:
            if debug:
                print token.type, token.value.encode('utf-8')
            if token.type == 'Word':
                print token.value.encode('utf-8')
