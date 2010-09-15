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
            ('Op', (r'[\[\]|:]',)),
            ('Regex', (r'<(\w|[-\[\]().^$\\])*>', re.UNICODE)),
            ('Name', (r'\w\w*',re.UNICODE))
            ]
    useless = ['Comment', 'NL', 'Space']
    t = make_tokenizer(specs)
    return [x for x in t(string) if x.type not in useless]

def parse(seq):
    'Sequence(Token) -> grammar dict'
    unarg = lambda f: lambda args: f(*args)
    tokval = lambda x: x.value
    joinif = lambda x: ''.join(i for i in x if i)
    n = lambda s: a(Token('Name', s)) >> tokval
    op = lambda s: a(Token('Op', s)) >> tokval
    regex = some(lambda t: t.type == 'Regex') >> tokval
    name = some(lambda t: t.type == 'Name') >> tokval
    re_or_string = regex | name 
    lemma = maybe(re_or_string) + op(':') + maybe(name) + op(':') + maybe(re_or_string) >> joinif
    fullgloss = forward_decl()
    glosslist = skip(op('[')) + many(fullgloss) + skip(op(']')) 
    fullgloss.define(lemma + maybe(glosslist) >> unarg(Gloss))
    pattern = skip(n('pattern')) + fullgloss + skip(op('|')) + fullgloss >> unarg(Pattern)
    sec_header = skip(n('section')) + name 
    section = sec_header + many(pattern) >> tuple
    grammar = many(section) + skip(finished) >> dict

    return grammar.parse(seq)

import unittest

class TestGrammarParser(unittest.TestCase):

    def setUp(self):
        self.minimal = 'section n pattern :: | ::'
        self.gmin = dict([('n', [Pattern(Gloss(u'::'), Gloss(u'::'))])])
        self.real = """
        # some comment
        section n
        pattern :: [ <[^n]$>:: la::] | :v: [:v: ::PROG]
        """
        self.greal = dict([('n', [Pattern(Gloss(u'::', [Gloss(u'<[^n]$>::'), Gloss(u'la::')]), Gloss(u':v:', [Gloss(u':v:'), Gloss(u'::PROG')]))])])

    def test_parser(self):
        self.assertEquals(self.gmin, parse(tokenize(self.minimal)))
        self.assertEquals(self.greal, parse(tokenize(self.real)))

if __name__ == '__main__':
    unittest.main()
