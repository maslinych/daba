#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import formats
import sys
from collections import defaultdict

def main():
    aparser = argparse.ArgumentParser(description='Daba suite. Metadata pretty printer.')
    aparser.add_argument('infile', help='Input file (.html)')
    aparser.add_argument('-f', '--field', dest='fields', action='append', help='Metadata field name')
    aparser.add_argument('-w', '--words', dest='fields', action='append_const', const='_auto:words', help='Number of word tokens in document')
    aparser.add_argument('-s', '--sentences', dest='fields', action='append_const', const='_auto:sentences', help='Number of sentences in document')
    aparser.add_argument('-p', '--paragraphs', dest='fields', action='append_const', const='_auto:paragraphs', help='Number of paragraphs in document')
    aparser.add_argument('-d', '--delimeter', action='store', default="\t", help='Delimiter for output fields')
    aparser.add_argument('-a', '--all', action='store_true', help='Print all metadata found in a file')
    args = aparser.parse_args()

    reader = formats.HtmlReader(args.infile, onlymeta=True)
    meta = defaultdict(unicode)
    for k,v in reader.metadata:
        meta[k] = v

    sys.stdout.write(unicode(args.infile).encode('utf-8'))

    if args.all:
        sys.stdout.write('\n')
        for name in sorted(meta.iterkeys()):
            sys.stdout.write(u"\t".join([name, meta[name]]).encode('utf-8'))
            sys.stdout.write('\n')
        sys.stdout.write('\n\n')
    else:
        sys.stdout.write(args.delimeter)
        sys.stdout.write(args.delimeter.join([meta[field] for field in args.fields]).encode('utf-8'))
        sys.stdout.write('\n')

if __name__ == '__main__':
    main()
