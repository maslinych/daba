#!/usr/bin/python
# -*- coding: utf-8 -*-

# SYNOPSIS: <outfile> <infiles...>
import formats
import sys

metadata = []
para = []

for i in range(2,len(sys.argv)):
    infile = formats.HtmlReader(sys.argv[i])
    metadata = infile.metadata
    para.extend(infile.glosses)

outfile = formats.HtmlWriter((metadata, para), sys.argv[1])
outfile.write()

