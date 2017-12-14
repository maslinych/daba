#!/usr/bin/python
# -*- coding: utf8 -*-

# fix older parser bug with long ps lists for inflected forms

import argparse
import formats

def main():

    aparser = argparse.ArgumentParser(description='Fix multiple ps')
    aparser.add_argument('infile', help='Input file (.html)')
    aparser.add_argument('-o', '--outfile', help='Output file', default=None)
    args = aparser.parse_args()

    handler = formats.HtmlReader(args.infile)
    for gloss, index in handler.itergloss():
        if not gloss.gloss and len(gloss.ps) > 1 and gloss.morphemes:
            stemps = [m.ps for m in gloss.morphemes if 'mrph' not in m.ps]
            if len(stemps) == 1 and stemps[0].issubset(gloss.ps):
                print gloss, '->',
                gloss = gloss._replace(ps = stemps[0])
                print gloss
                handler.setgloss(gloss, index)

    out = formats.HtmlWriter((handler.metadata, handler.glosses), args.outfile or args.infile)
    out.write()

if __name__ == '__main__':
    main()
