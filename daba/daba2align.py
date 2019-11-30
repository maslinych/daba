#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import daba.formats


def token_iterator(infile, select_types=('</s>',)):
    reader = daba.formats.HtmlReader(infile)
    for token in reader:
        if token.type in select_types:
            yield token


def token_printer(token, number):
    return u'<{0} n="{1}">{2}</{0}>\n'.format('s', number, token.value.strip())


def main():
    def parse_arguments():
        parser = argparse.ArgumentParser(
            description='Parallel corpus alignment helper')
        parser.add_argument('infile', help='Input file (daba html format)')
        parser.add_argument('outfile', help='Output file (txt)')
        return parser.parse_args()
    args = parse_arguments()

    with open(args.outfile, 'w', encoding='utf-8') as out:
        for n, t in enumerate(token_iterator(args.infile)):
            out.write(token_printer(t, n))


if __name__ == '__main__':
    main()
