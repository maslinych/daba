#!/usr/bin/python
# -*- coding: utf8 -*-

import argparse
import formats
import grammar
from ntgloss import Gloss
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError

def parse_gloss(gloss_string):
    return grammar.fullgloss_parser().parse(grammar.tokenize(gloss_string))

def main():

    aparser = argparse.ArgumentParser(description='Stream editor for files in Daba format')
    aparser.add_argument('infile', help='Input file (.html)')
    aparser.add_argument('-o', '--outfile', help='Output file', default=None)
    aparser.add_argument('-s', '--script', help='File with edit commands', required=True)
    args = aparser.parse_args()

    # parse script file
    commands_list = []
    with open(args.script) as commands:
        for command in commands:
            try:
                source, target = command.decode('utf8').strip('\n').split()
                try:
                    ingloss = parse_gloss(source)
                    outgloss = parse_gloss(target)
                    commands_list.append((ingloss,outgloss))
                except (LexerError, NoParseError) as e:
                   print unicode(e)
            except (ValueError):
                print 'Invalid command: {0}'.format(command)

    def recursive_match(gloss, pattern, target):
        if gloss.matches(pattern):
            out = target
        else:
            out = gloss
        if gloss.morphemes:
            out._replace(morphemes=tuple([recursive_match(m, pattern, target)] for m in gloss.morphemes))
        return out

    # replace glosses
    in_handler = formats.HtmlReader(args.infile)
    for pp, par in enumerate(in_handler.glosses):
        for sp, sent in enumerate(par):
            for pos, token in enumerate(sent[1]):
                if token[0] == 'w':
                    for gpos, gloss in enumerate(formats.GlossToken(token).glosslist):
                        for ingloss, outgloss in commands_list:
                            matched = recursive_match(gloss, ingloss, outgloss)
                            if not matched == gloss:
                                in_handler.glosses[pp][sp][1][pos][1][2][gpos] = outgloss

    out_handler = formats.HtmlWriter((in_handler.metadata, in_handler.glosses), args.outfile or args.infile)
    out_handler.write()

if __name__ == '__main__':
    main()
