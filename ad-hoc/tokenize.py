#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from mparser import Tokenizer

tkz = Tokenizer()

with open(sys.argv[1]) as f:
    txt = f.read().decode("utf-8")
    for sent in tkz.split_sentences(tkz.tokenize(txt)):
        print "SENT"
        for token in sent:
            print token.type, token.value.encode('utf-8')
