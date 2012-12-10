#!/usr/bin/python
# -*- coding: utf8 -*-

import argparse
import formats
import grammar
from ntgloss import Gloss
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError
import unicodedata as u

def parse_gloss(gloss_string):
    return grammar.fullgloss_parser().parse(grammar.tokenize(gloss_string))

def recursive_match(gloss, pattern, target):
    status = False
    if gloss.matches(pattern):
        status = True
        out = gloss.union(target, psoverride=True)
    else:
        out = gloss
        if gloss.morphemes:
            morphlist, statuslist = zip(*[recursive_match(m, pattern, target) for m in gloss.morphemes])
            out = out._replace(morphemes=morphlist)
            if not status:
                status = any(statuslist)
    return (out, status)


def main():

    aparser = argparse.ArgumentParser(description='Stream editor for files in Daba format')
    aparser.add_argument('infile', help='Input file (.html)')
    aparser.add_argument('-o', '--outfile', help='Output file', default=None)
    aparser.add_argument('-s', '--script', help='File with edit commands', required=True)
    args = aparser.parse_args()

    if not args.outfile:
        args.outfile = args.infile
    # parse script file
    print 'Processing', args.infile, 'with rules from', args.script, '...'
    commands_list = []
    with open(args.script) as commands:
        for command in commands:
            if not command.isspace():
                try:
                    source, sep, target = u.normalize('NFKD', command.decode('utf8')).strip('\n').partition('>>')
                    source = source.strip()
                    target = target.strip()
                    try:
                        ingloss = parse_gloss(source)
                        outgloss = parse_gloss(target)
                        commands_list.append((ingloss,outgloss))
                    except (LexerError, NoParseError) as e:
                        print 'In rule: {0}'.format(command)
                        print unicode(e)
                except (ValueError):
                    print 'Invalid command: {0}'.format(command)


    # replace glosses
    dirty = False
    in_handler = formats.HtmlReader(args.infile)
    for gloss, index in in_handler.itergloss():
        for ingloss, outgloss in commands_list:
            matched, status = recursive_match(gloss, ingloss, outgloss)
            if status:
                dirty = True
                in_handler.setgloss(matched, index)
                #NB: rule application should has side effect (like in sed)
                print u'{0} -> {1}'.format(gloss, matched).encode('utf-8')
                gloss = matched

    if dirty:
        out_handler = formats.HtmlWriter((in_handler.metadata, in_handler.glosses), args.outfile)
        out_handler.write()
        print 'Written', args.outfile

if __name__ == '__main__':
    main()
