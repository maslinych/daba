#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

with open(sys.argv[1]) as f:
    for line in f:
        l = line
        l = l.replace(u'\u04b4', r"ɔ")
        l = l.replace(u'\u03ef', r"ɛ")
        l = l.replace(u'\u0652', r"ɲ")
        l = l.replace(u'\u0b02', r"Ɲ")
        l = l.replace(u'\u08aa', r"Ŋ")
        l = l.replace(u'\u089c', r"Ɔ")
        l = l.replace(u'\u07d7', r"Ɛ")

        sys.stdout.write(l)
        sys.stdout.write('\n')
