#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SYNOPSIS: <outfile> <infiles...>
import daba.formats
import sys

metadata = []
para = []

for i in range(2,len(sys.argv)):
    infile = daba.formats.HtmlReader(sys.argv[i])
    metadata = infile.metadata
    para.extend(infile.glosses)

outfile = daba.formats.HtmlWriter((metadata, para), sys.argv[1])
outfile.write()

