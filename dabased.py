#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
import argparse
import formats
import grammar
from ntgloss import Gloss
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError
from itertools import tee, izip
import unicodedata as u

getstr = lambda s: u' ++ '.join([unicode(g) for g in zip(*s)[0]])

def parse_gloss(gloss_string):
    return grammar.fullgloss_parser().parse(grammar.tokenize(gloss_string))

def recursive_match((gloss, index), pattern):
    status = False
    if gloss.matches(pattern):
        return True
    elif gloss.morphemes:
        return any([recursive_match((morph, index), pattern) for morph in gloss.morphemes])
    return False

def recursive_replace((gloss, index), pattern, target):
    if gloss.matches(pattern):
        out = gloss.union(target, psoverride=True)
    else:
        out = gloss
    if gloss.morphemes:
        out = out._replace(morphemes=tuple(zip(*[recursive_replace((morph, index), pattern, target) for morph in gloss.morphemes])[0]))
    return (out, index)

def window(iterable, size):
    iters = tee(iterable, size)
    for i in xrange(1, size):
        for each in iters[i:]:
            next(each, None)
    return izip(*iters)

def parse_expr(expr):
    glosslist = [i.strip() for i in expr.partition('++') if not i in ['++', '']]
    result = []
    for gexpr in glosslist:
        try:
            result.append(parse_gloss(gexpr))
        except (LexerError, NoParseError) as e:
            sys.stderr.write('In rule: {0}'.format(gexpr))
            sys.stderr.write(unicode(e) + '\n')
            return []
    return result

def parse_command(command):
    try:
        source, sep, target = u.normalize('NFKD', command.decode('utf8')).strip('\n').partition('>>')
    except (ValueError):
        sys.stderr.write('Invalid command: {0}\n'.format(command))
        return
    sourcelist = parse_expr(source)
    targetlist = parse_expr(target)
    if not len(sourcelist) == len(targetlist):
        sys.stderr.write('Invalid command: pattern/replacement of unequal length: {0}\n'.format(command))
        return
    return (sourcelist, targetlist)

def process_file(infile, outfile, commands_list):
    # replace glosses
    dirty = False
    in_handler = formats.HtmlReader(infile)
    for inlist, outlist in commands_list:
        winsize = len(inlist)
        for glosslist in window(in_handler.itergloss(), winsize):
            replacelist = []
            # FIXME special case for 1:1 replacement: allows deep matching
            if len(inlist) == len(outlist) == 1:
                if recursive_match(glosslist[0], inlist[0]):
                    replacelist = [recursive_replace(glosslist[0], inlist[0], outlist[0])]
            # all other cases: replace only on top level
            elif all(gloss.matches(pattern) for ((gloss, index), pattern) in zip(glosslist, inlist)):
                for ((gloss, index), pattern) in zip(glosslist, outlist):
                    replacelist.append((gloss.union(pattern, psoverride=True), index))
            if replacelist:
                dirty = True
                for (replacement, index) in replacelist:
                    in_handler.setgloss(replacement, index)
                #NB: rule application should has side effect (like in sed)
                print u'{0} -> {1}'.format(getstr(glosslist), getstr(replacelist)).encode('utf-8')

    if dirty:
        out_handler = formats.HtmlWriter((in_handler.metadata, in_handler.glosses), outfile)
        out_handler.write()
    return dirty


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
                commands_list.append(parse_command(command))
        commands_list = filter(None, commands_list)
        dirty = process_file(args.infile, args.outfile, commands_list)
        if dirty:
            print 'Written', args.outfile

if __name__ == '__main__':
    main()
