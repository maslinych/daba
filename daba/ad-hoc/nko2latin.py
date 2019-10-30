#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from plugins import OrthographyConverter

def load_plugins():
    plugindir = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), '..', 'plugins')
    plugins = [x[:-3] for x in os.listdir(plugindir) if x.endswith('.py') and not x.startswith('__')]
    for plugin in plugins:
        mod = __import__('.'.join(['plugins', plugin]))


load_plugins()
converter = OrthographyConverter.get_plugins()["nko"]

for line in open(sys.argv[1]):
    ws = line.decode("utf-8").strip().split()
    print(' '.join([converter.convert(w)[0] for w in ws]).encode('utf-8'))
        

