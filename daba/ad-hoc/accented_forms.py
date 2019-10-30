#!/usr/bin/env python3
from bamana import test
from orthograph import *

for w in test.words():
    res = convertw(w)
    if res[0] != detone(res[0]):
        print(w.encode('utf-8'))
