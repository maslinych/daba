#!/usr/bin/python
# -*- coding: utf-8 -*-

r"""Dabased is a stream editor (sed) for files with linguistic
annotation in Daba format.

Dabased performs batch replacements in daba annotation accorging to
the rules defined in a script file. For each rule, dabased runs
through the annotated tokens in daba file trying to apply the
transformation defined by the rule as many times as possible. Text
segments where the rule is applied can not overlap.

Script file syntax
==================

Rules
-----

Dabased script file is a simple text file with a list of replacement
rules to apply to a file, one rule on a line. Empty lines and lines
starting with # symbol are ignored.

Each rule has a form::

    pattern >> replacement

where

 * a pattern is an expression that defines a fragment of annotation
   that the rule matches;
 * a replacement is a list of tokens to insert.

Expressions
-----------

Each expression is a list of tokens separated by '++'.
Each token may be either:

* a Gloss in a unicode notation::

    words:n:gloss [word:n:gloss s:mrph:PL]

A Gloss may be not fully specified. If such a partial expression
appears in the left side of the rule (a pattern), the match is
perfomed accorging to :method:`Gloss.matches()` logic. If a partial
expression appears in the replacement part, the information in the
source token and the replacement pattern is united according to
:method:`Gloss.union()` logic.

* a GlossToken, in the following syntax:

    @type

or

    @type:regex

where

* type — is a string matching `GlossToken.type`;
* regex — is a regular expression that is matched against the whole
  `GlossToken.value`.

The GlossToken expressions are not meant to be used for 'w' token type
(regular words). Use Gloss expressions instead.

Expression Examples
-------------------

* :n: — matches any noun

* he:pers:3SG — matches personal pronoun 'he' with specified
part of speech tag and gloss.

* :pers: ++ :v: — matches personal pronoun followed by any verb

* @<s> ++ @</s> — matches a sentence opening tag immediately followed
  by a sentence closing tag (an empty sentence).

* @</s>:\n+ — matches a sentence closing tag where sentence text
  consists only of one or more newline symbols (no words in a
  sentence).

Types of Rules
--------------

There are three distinct types of rules with slightly different
replacement logic.

1. One-to-one Gloss replacement rule:

    he:pers:HE >> he:pers:3SG

This is the most common and historically the first use case for
dabased. It is used to tweak glosses and other annotation fields for
the text that has already been annotated.

Note that the rule of this type is applyied recursively to all
embedded glosses (morhemes at any level of annotation). This allows to
make replacements in stems occurring in any compound and derivative
forms.

2. Many-to-many replacement rules:

    @<s> ++ i:pers:1sg >> @<s> ++ i:pers:1sg

This type of rules applies to a window of several sequential tokens,
either word tokens (Glosses) or others. The replacement part should
have an equal number of tokens. The replcement is perfomed using
:method:`GlossToken.union()` in the given order. The union is done
only for the root Glosses, morphemes are not processed recursively.

3. Asymmetric replacement rules:

    @<s> ++ @</s> >>

Asymmetric rules are any rules that have different number of tokens on
the left and right sides of the rule. The replacement part of these
rules is simply substituted instead of a list of source tokens where
the rule matches. No union is done wth the source tokens, so the
replacement tokens should be fully specified (no partial Glosses are
allowed).

Asymmetric rules may be used for token splitting and merging. A
special case of asymmetric rules are deletion rules, with an empty
right side.
"""


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
#        for token, intoken in zip(tokenlist, pattern):
#            sys.stderr.write(
#                u'{}\tIN: {} PAT: {}\n'.format(
#                    token.matches(intoken, psstrict=True),
#                    token,
#                    intoken
#                ).encode('utf-8')
#            )
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
                if rule.inlist[0].gloss.morphemes and rule.outlist[0].gloss.morphemes:
                    def replace_func(tokens, rule):
                        token = tokens[0]
                        target = rule.outlist[0]
                        gt = self.replace(token, target)
                        outgloss = gt.gloss._replace(morphemes=target.gloss.morphemes)
                        gt.w(outgloss, 'dabased', token=token.token)
                        return [gt]
                    domatch = True
                else:
                    def replace_func(tokens, rule):
                        token = tokens[0].gloss
                        pattern = rule.inlist[0].gloss
                        target = rule.outlist[0].gloss
                        outgloss = self.recursive_replace(token, pattern, target)
                        gt = formats.GlossToken()
                        gt.w(outgloss, 'dabased', token=token.token)
                        if pattern.ps == target.ps:
                            return [tokens[0].union(gt)]
                        else:
                            return [gt]
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
#        sys.stderr.write(u'Domatch {}\n'.format(str(domatch)))
        success = -rule.winsize
        for pos, tokens in self.feed_tokens(rule.winsize, stream):
            if pos < success + rule.winsize:
                continue
            if (
                    (not domatch and tokens[0].type == 'w')
                    or
                    (domatch and self.match(tokens, rule.inlist))
            ):
#                sys.stderr.write(
#                    u'match: {}\n'.format(self.getstr(tokens)).encode('utf-8')
#                )
                replacement = replace_func(tokens, rule)
#                sys.stderr.write(
#                    u'replacement: {}\n'.format(self.getstr(replacement)).encode('utf-8')
#                )
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
