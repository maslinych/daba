#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import re
import argparse
import formats
import grammar
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError
from collections import namedtuple
from itertools import islice, izip_longest
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
        gloss = grammar.fullgloss_parser().parse(
            grammar.tokenize(gloss_string)
        )
        gt = formats.GlossToken()
        gt.w(gloss, 'dabased')
        return gt

    def parse_token(self, token_expression):
        try:
            toktype, tokvalue = token_expression[1:].split(':')
            tokvalue = re.compile("^" + tokvalue + "\Z", re.UNICODE)
        except (ValueError):
            toktype = token_expression[1:]
            tokvalue = ''
        return formats.GlossToken((toktype, tokvalue))

    def parse_expr(self, expr):
        glosslist = [i.strip()
                     for i in re.split(r'\+\+', expr)
                     if i not in ['++', ''] and not i.isspace()]
        result = []
        for gexpr in filter(None, glosslist):
            try:
                if gexpr.startswith('@'):
                    result.append(self.parse_token(gexpr))
                else:
                    result.append(self.parse_gloss(gexpr))
            except (LexerError, NoParseError, ValueError) as e:
                sys.stderr.write(u'In rule: {0}'.format(gexpr).encode('utf-8'))
                sys.stderr.write(u'{}\n'.format(e).encode('utf-8'))
                return []
        return result

    def parse_command(self, command):
        try:
            source, sep, target = u.normalize(
                'NFKD', command.decode('utf8')
            ).strip('\n').partition('>>')
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
        return u' ++ '.join([unicode(token) for token in tokens])

    def feed_tokens(self, winsize, stream=()):
        pos = 0
        it = iter(stream)
        window = tuple(islice(it, winsize))
        if len(window) == winsize:
            yield pos, window
        for token in it:
            window = window[1:] + (token,)
            pos += 1
            yield pos, window

    def match(self, tokenlist, pattern):
        return all(
            token.matches(intoken, psstrict=True)
            for token, intoken in zip(tokenlist, pattern)
        )

    def replace(self, token, target):
        if token.type == 'w':
            gt = formats.GlossToken()
            gt.w(target.gloss, 'dabased')
            outgloss = token.union(gt)
            return outgloss
        else:
            return target

    def recursive_replace(self, gloss, pattern, target):
        if gloss.matches(pattern, psstrict=True):
            out = gloss.union(target, psoverride=True)
        else:
            out = gloss
        if gloss.morphemes:
            out = out._replace(
                morphemes=tuple(
                    self.recursive_replace(morph, pattern, target)
                    for morph in gloss.morphemes)
            )
        return out

    def make_replace_func(self, rule):
        if not rule.symmetric:
            def replace_func(tokens, rule):
                return rule.outlist
            domatch = True
        else:
            # FIXME special case for 1:1 replacement: allows deep matching
            if rule.winsize == 1 and rule.inlist[0].type == 'w':
                def replace_func(tokens, rule):
                    token = tokens[0].gloss
                    pattern = rule.inlist[0].gloss
                    target = rule.outlist[0].gloss
                    outgloss = self.recursive_replace(token, pattern, target)
                    gt = formats.GlossToken()
                    gt.w(outgloss, 'dabased')
                    return [tokens[0].union(gt)]
                domatch = False
            else:
                def replace_func(tokens, rule):
                    return [self.replace(token, target)
                            for token, target
                            in zip(tokens, rule.outlist)]
                domatch = True
        return (domatch, replace_func)

    def apply_rule(self, rule, stream):
        domatch, replace_func = self.make_replace_func(rule)
        success = -rule.winsize
        for pos, tokens in self.feed_tokens(rule.winsize, stream):
            if pos < success + rule.winsize:
                continue
            if (
                    (not domatch and tokens[0].type == 'w')
                    or
                    (domatch and self.match(tokens, rule.inlist))
            ):
                replacement = replace_func(tokens, rule)
                if not all(g == r for g, r
                           in izip_longest(
                               tokens,
                               replacement,
                               fillvalue=formats.GlossToken())):
                    self.dirty = True
                    if self.verbose:
                        sys.stderr.write(
                            u'{0} -> {1}\n'.format(
                                self.getstr(tokens),
                                self.getstr(replacement)).encode('utf-8')
                            )
                    tokens = replacement
                    success = pos
                    for token in tokens:
                        yield token
                    continue
            yield tokens[0]
        else:
            for token in tokens[1:]:
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
