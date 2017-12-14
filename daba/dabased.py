#!/usr/bin/python
# -*- coding: utf8 -*-

import sys
import re
import argparse
import formats
import grammar
from ntgloss import Gloss
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError
from collections import namedtuple
import unicodedata as u


class ReplaceRule(namedtuple('ReplaceRule', 'inlist outlist')):
    __slots__ = ()

    @property
    def winsize(self):
        return len(self.inlist)

    @property
    def symmetric(self):
        return len(self.inlist) == len(self.outlist)


class ScriptParser(object):
    def __init__(self, scriptfile):
        self.commands_list = []
        with open(scriptfile) as script:
            for command in script:
                if not command.isspace() and not command.startswith('#'):
                    self.commands_list.append(self.parse_command(command))
        self.commands_list = filter(None, self.commands_list)

    def __iter__(self):
        for rule in self.commands_list:
            yield rule

    def parse_gloss(self, gloss_string):
        return grammar.fullgloss_parser().parse(grammar.tokenize(gloss_string))

    def parse_expr(self, expr):
        glosslist = [i.strip() for i in re.split(r'\+\+', expr) if not i in ['++', '']]
        result = []
        for gexpr in glosslist:
            try:
                result.append(self.parse_gloss(gexpr))
            except (LexerError, NoParseError) as e:
                sys.stderr.write(u'In rule: {0}'.format(gexpr).encode('utf-8'))
                sys.stderr.write(u'{}\n'.format(e).encode('utf-8'))
                return []
        return result

    def parse_command(self, command):
        try:
            source, sep, target = u.normalize('NFKD', command.decode('utf8')).strip('\n').partition('>>')
        except (ValueError):
            sys.stderr.write('Invalid command: {0}\n'.format(command))
            return
        sourcelist = self.parse_expr(source)
        targetlist = self.parse_expr(target)
        return ReplaceRule(sourcelist, targetlist)


class StreamEditor(object):
    def __init__(self, verbose=False):
        self.dirty = False
        self.verbose = verbose

    def getstr(self, tokens):
        return u' ++ '.join([unicode(gloss) for gloss in tokens])

    def feed_tokens(self, winsize, stream=()):
        window = []
        for token in stream:
            window.append(token)
            if len(window) == winsize and all([t.type == 'w' for t in window]):
                yield (True, tuple(window))
                window = window[1:]
            else:
                yield (False, tuple(window))
                window = []

    def match(self, glosslist, pattern, recursive=False):
        return all(gloss.matches(ingloss, psstrict=True) for gloss, ingloss in zip(glosslist, pattern))

    def replace(self, glosslist, target, recursive=False):
        return tuple(gloss.union(outgloss, psoverride=True) for gloss, outgloss in zip(glosslist, target))

    def recursive_replace(self, gloss, pattern, target):
        if gloss.matches(pattern, psstrict=True):
            out = gloss.union(target, psoverride=True)
        else:
            out = gloss
        if gloss.morphemes:
            out = out._replace(morphemes=tuple(self.recursive_replace(morph, pattern, target) for morph in gloss.morphemes))
        return out

    def make_replace_func(self, rule):
        # FIXME special case for 1:1 replacement: allows deep matching
        if rule.symmetric and rule.winsize == 1:
            replace_func = lambda tokens, rule: tuple(self.recursive_replace(gloss, pattern, target) for gloss, pattern, target in zip(tokens, rule.inlist, rule.outlist)) 
            domatch = False
        elif not rule.symmetric:
            replace_func = lambda tokens, rule: rule.outlist
            domatch = True
        else:
            replace_func = lambda tokens, rule: self.replace(tokens, rule.outlist)
            domatch = True
        return (domatch, replace_func)

    def extract_glosses(self, tokens):
        # FIXME: only first gloss in variants list is checked, others ignored
        return [gt.glosslist[0] for gt in tokens]

    def insert_glosses(self, tokens, glosslist):
        out = []
        if len(tokens) == len(glosslist):
            for token, gloss in zip(tokens, glosslist):
                token.glosslist[0] = gloss
                out.append(token)
        else:
            out = [formats.GlossToken(('w', (gloss.form, 'dabased', [gloss]))) for gloss in glosslist]
        return out

    def apply_rule(self, rule, stream):
        domatch, replace_func = self.make_replace_func(rule)
        for tocheck, tokens in self.feed_tokens(rule.winsize, stream):
            if tocheck:
                glosslist = self.extract_glosses(tokens)
                if (not domatch) or (domatch and self.match(glosslist, rule.inlist)):
                    replacement = replace_func(glosslist, rule)
                    if not all(g==r for g, r in zip(glosslist, replacement)):
                        self.dirty = True
                        tokens = self.insert_glosses(tokens, replacement)
                        if self.verbose:
                            sys.stderr.write(u'{0} -> {1}\n'.format(self.getstr(glosslist), self.getstr(replacement)).encode('utf-8'))
            for token in tokens:
                yield token

    def apply_script(self, script, stream):
        tokens = stream
        for rule in script:
            tokens = self.apply_rule(rule, list(tokens))
        return tokens


def main():

    aparser = argparse.ArgumentParser(description='Stream editor for files in Daba format')
    aparser.add_argument('infile', help='Input file (.html)')
    aparser.add_argument('-o', '--outfile', help='Output file', default=None)
    aparser.add_argument('-s', '--script', help='File with edit commands', required=True)
    aparser.add_argument('-v', '--verbose', help='Print info messages', action='store_true')
    args = aparser.parse_args()
    if not args.outfile:
        args.outfile = args.infile
    # start processing
    if args.verbose:
        sys.stderr.write(u'Processing {0} with rules from {1}...\n'.format(args.infile, args.script).encode('utf-8'))
    sed = StreamEditor(verbose=args.verbose)
    script = ScriptParser(args.script)
    in_handler = formats.HtmlReader(args.infile, compatibility_mode=False)
    processed_tokens = list(sed.apply_script(script, in_handler))
    if sed.dirty:
        out_handler = formats.HtmlWriter((in_handler.metadata, in_handler.make_compatible_glosses(processed_tokens)), args.outfile)
        out_handler.write()
        if args.verbose:
            sys.stderr.write(u'Written {0}\n'.format(args.outfile).encode('utf-8'))

if __name__ == '__main__':
    main()
