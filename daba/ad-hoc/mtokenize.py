#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from daba.mparser import Tokenizer

debug = True

tkz = Tokenizer()

with open(sys.argv[1], encoding="utf-8") as f:
    txt = f.read()
    for sent in tkz.split_sentences(tkz.tokenize(txt)):
        if debug:
            print("")
            print("SENT")
        for token in sent:
            if debug:
                print(token.type, token.value)
            if token.type == 'Word':
                print(token.value)
