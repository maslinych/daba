#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

with open(sys.argv[1]) as f:
    for line in f:
        l = line.decode('utf-8')
        l = l.replace(u'\u04b4', ur"ɔ")
        l = l.replace(u'\u03ef', ur"ɛ")
        l = l.replace(u'\u0652', ur"ɲ")
        l = l.replace(u'\u0b02', ur"Ɲ")
        l = l.replace(u'\u08aa', ur"Ŋ")
        l = l.replace(u'\u089c', ur"Ɔ")
        l = l.replace(u'\u07d7', ur"Ɛ")

        sys.stdout.write(l.encode('utf-8'))
        sys.stdout.write('\n')
