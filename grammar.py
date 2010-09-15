#!/usr/bin/python
# -*- encoding: utf-8 -*-

import re
from objects import Pattern, Gloss
from funcparserlib.parser import *
from funcparserlib.lexer import make_tokenizer, Token, LexerError

def tokenize(string):
    'unicode -> Sequence(Token)'
    specs = [
            ('Comment', (r'#.*',)),
            ('NL', (r'[\r\n]+',)),
            ('Space', (r'[ \t\r\n]+',)),
            ('Op', (r'[\[\]|]',)),
            ('Gloss', (r'\w*:\w*:\w*', re.UNICODE)),
            ('Name', (r'\w\w*',re.UNICODE))
            ]
    useless = ['Comment', 'NL', 'Space']
    t = make_tokenizer(specs)
    return [x for x in t(string) if x.type not in useless]

def parse(seq):
    'Sequence(Token) -> object'
    unarg = lambda f: lambda args: f(*args)
    tokval = lambda x: x.value
    n = lambda s: a(Token('Name', s)) >> tokval
    op = lambda s: a(Token('Op', s)) >> tokval
    lemma = some(lambda t: t.type == 'Gloss') >> tokval
    name = some(lambda t: t.type == 'Name') >> tokval
    fullgloss = forward_decl()
    glosslist = skip(op('[')) + many(fullgloss) + skip(op(']')) 
    fullgloss.define(lemma + maybe(glosslist) >> unarg(Gloss))
    pattern = fullgloss + skip(op('|')) + fullgloss >> unarg(Pattern)
    sec_header = skip(n('section')) + name 
    section = sec_header + many(pattern) >> tuple
    grammar = many(section) + skip(finished)

    return grammar.parse(seq)

import unittest

class TestGrammarParser(unittest.TestCase):

    def setUp(self):
        self.minimal = 'section n :: | ::'
        self.gmin = [('n', [Pattern(Gloss(u'::'), Gloss(u'::'))])]

    def test_parser(self):
        self.assertEquals(self.gmin, parse(tokenize(self.minimal)))

if __name__ == '__main__':
    unittest.main()
