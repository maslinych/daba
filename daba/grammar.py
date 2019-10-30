#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import re
from ntgloss import Pattern, Gloss
from funcparserlib.parser import *
from funcparserlib.lexer import make_tokenizer, Token, LexerError

PSLIST = [
        'mrph',
        'n.prop',
        'n',
        'adj',
        'num',
        'v',
        'ptcp',
        'vq',
        'adv',
        'adv.p',
        'onomat',
        'intj',
        'conj',
        'prt',
        'cop',
        'dtm',
        'pers',
        'pm',
        'pp',
        'prn',
        'prep',
        'n.top',
        'conv.n',
        'PUNCT',
        ]


def tokenize(string):
    'unicode -> Sequence(Token)'
    specs = [
            ('Comment', (r'#.*',)),
            ('NL', (r'[\r\n]+',)),
            ('Space', (r'[ ]+',)),
            ('JunkSpace', (r'[\t]+',)),
            ('Op', (r'[\[\]|:{}]',)),
            #('Regex', (r'<(\w|[-={}\[\]|().,^$+*?:\\])*>', re.UNICODE)),
            ('Regex', (r'<re>.*?</re>', re.UNICODE)),
            ('QuotedName', (r'"[^"\n]+"', re.UNICODE)),
            ('Name', (r'[^:<>\[\]{}| \n]+', re.UNICODE)),
            #('Name', (r"(\w[\u0300\u0301\u0302]?)+([-./](\w[\u0300\u0301\u0302]?)+)*['\u2019]?",re.UNICODE)),
            #('Name', (r'(\w[\u0300\u0301]?([-./](\w[\u0300\u0301]?)+)*|[-0-9][-0-9]*)',re.UNICODE))
            ]
    useless = ['Comment', 'NL', 'JunkSpace']
    tok = make_tokenizer(specs)
    #print("DEBUG TOKENIZER: ", [x for x in tok(string)])
    return [x for x in tok(string) if x.type not in useless]
    

def unwrap_re(tupl):
    unre = lambda s: s[4:-5]
    if not isinstance(tupl, tuple):
        return re.compile(r'^(?P<__group0>{0})$'.format(unre(tupl)))
    unfolded = []
    for i,part in enumerate(tupl):
        # FIXME: to be done by formparser
        #if part.startswith(('') and part.endswith('',)):
        #    part = part[4:-5]
        if not part:
            part = '.+'
        elif part.startswith('<re>'):
            part = unre(part)
        unfolded.append(r'(?P<__group{0}>{1})'.format(i,part))
    return re.compile(r'^{0}$'.format(''.join(unfolded)))

tokval = lambda x: x.value
unquote = lambda s: s.strip('"')
name = some(lambda t: t.type in ['Name', 'QuotedName']) >> tokval >> unquote
pslabel = some(lambda t: t.value in PSLIST) >> tokval
space = some(lambda t: t.type == 'Space') >> tokval
op = lambda s: a(Token('Op', s)) >> tokval
op_ = lambda s: skip(op(s))
foldl = lambda s: [s]
unfoldl = lambda l: [k for j in [i for i in l if i] for k in j]
unarg = lambda f: lambda args: f(*args)
joinif = lambda x: ''.join(i for i in x if i)
denone = lambda s: s or ()
maketuple = lambda t: tuple(t.split('/')) if t else ()
denonetuple = lambda t: t or ()
filternone = lambda s: [i for i in s if i]
despace = lambda s: [i for i in s if s is not ' ']

def flatten_list(l):
    for el in l:
        if isinstance(el, list) and not isinstance(el, basestring):
            for sub in flatten_list(el):
                yield sub
        else:
            yield el

def str_tokenize(string):
    'unicode -> Sequence(Token)'
    specs = [
            ('JunkSpace', (r'[\r\n\t]+',)),
            ('Space', (r'[ ]+',)),
            ('Op', (r'[:/\[\]]',)),
            ('Name', (r'[^:/ \[\]\r\t\n]+', re.UNICODE)),
            ]
    useless = ['JunkSpace']
    tok = make_tokenizer(specs)
    return [x for x in tok(string) if x.type not in useless]

def stringgloss_parser():
    ps = pslabel + maybe(many(op_('/') + pslabel)) >> flatten_list >> tuple
    lemma = name + op_(':') + ( maybe(ps) >> denonetuple ) + op_(':') + maybe(name) 
    fullgloss = forward_decl()
    glosslist = skip(space) + op_('[') + fullgloss + maybe( many( skip(space) + fullgloss ) ) + op_(']') >> flatten_list >> filternone >> tuple
    fullgloss.define(lemma + ( maybe(glosslist) >> denone ) >> unarg(Gloss))
    grammar = fullgloss + skip(finished)

    return grammar


def fullgloss_parser():
    regex = some(lambda t: t.type == 'Regex') >> tokval
    re_or_string = regex | name
    unregex = regex >> unwrap_re
    splitter = oneplus(op_('|') + maybe(re_or_string) ) >> tuple
    form_expr = op_('{') + (maybe(re_or_string) >> foldl) + splitter + op_('}') >> unfoldl >> tuple >> unwrap_re
    lemma = skip(maybe(space)) + maybe(form_expr | unregex | name) + op_(':') + (maybe(name) >> maketuple) + op_(':') + maybe(name | unregex)
    fullgloss = forward_decl()
    glosslist = skip(space) + skip(op('[')) + skip(maybe(space)) + many(fullgloss) + skip(maybe(space)) + skip(op(']')) >> tuple
    fullgloss.define(lemma + ( maybe(glosslist) >> denone ) >> unarg(Gloss))
#    fullgloss.define(lemma + maybe(glosslist) >> unarg(Gloss))

    return fullgloss


def parse(seq):
    'Sequence(Token) -> grammar dict'
    make_patterns = lambda x: ('patterns', x)
    n = lambda s: a(Token('Name', s)) >> tokval
    # plan syntax
    f_add = n('add') + skip(space)
    f_apply = n('apply') + skip(space)
    f_lookup = n('lookup') + skip(maybe(space))
    f_parallel = n('parallel') + skip(space)
    f_sequential = n('sequential') + skip(space)
    f_firstmatch = n('firstmatch') + skip(space)
    f_parse = n('parse') + skip(space) + name >> list
    f_decompose = n('decompose') + skip(space) + name >> list
    func_clause = oneplus(f_add | f_apply | f_lookup | f_parallel | f_sequential | f_firstmatch) + maybe(f_parse | f_decompose) >> unfoldl >> tuple
    stage_clause = skip(n('stage')) + skip(space) + name + skip(space) + func_clause + skip(maybe(space))
    return_clause = n('return') + skip(space) + skip(n('if')) + skip(space) + name + skip(maybe(space))
    for_clause = skip(n('for')) + skip(space) + name + skip(op(':')) + skip(maybe(space)) + many(stage_clause | return_clause ) >> tuple
    plan_dict = oneplus(for_clause) >> dict
    plan = n('plan') + skip(maybe(space)) + plan_dict  >> tuple
    # pattern syntax
    pattern = skip(n('pattern')) + skip(space) + fullgloss_parser() + skip(space) + skip(op('|')) + skip(space) + fullgloss_parser() + skip(maybe(space)) >> unarg(Pattern)
    sec_header = skip(n('section')) + skip(space) + name + skip(maybe(space))
    section = sec_header + many(pattern) 
    sections = many(section) >> dict
    patterns = sections >> make_patterns
    grammar = plan + patterns + skip(finished) >> dict

    return grammar.parse(seq)

def preprocess(gstring):
    mdict = {}
    lines = gstring.split('\n')
    for line in lines:
        if line.startswith('macro'):
            fields = line.split()
            mdict[fields[1]] = fields[2]
    filtered = '\n'.join(filter(lambda i: not i.startswith('macro'), lines))
    for macro,replacement in mdict.iteritems():
        filtered = filtered.replace(macro, replacement)
    return filtered


class Grammar(object):
    def __init__(self,filename,encoding='utf-8'):
        with open(filename, 'r', encoding=encoding) as gf:
            text = preprocess(gf.read())
            gdict = parse(tokenize(text))
            self.plan = gdict['plan']
            self.patterns = gdict['patterns']

import unittest

# FIXME: TESTS WITH OBSOLETE GLOSS SYNTAX
class TestGrammarParser(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.minimal = 'plan for token: stage 0 add lookup section n pattern :: | ::'
        self.gmin = {'patterns': {'n': [Pattern(Gloss(None, (), None, ()), Gloss(None, (), None, ()))]}, 'plan': {'token': [('0', ('add', 'lookup'))]}}
        self.real = """
plan for token: stage 0 add lookup
return if unparsed
# some comment
section n
pattern :: [ la::] | :v: [:v: ::PROG]
"""
        self.greal = {'patterns': {'n': [Pattern(Gloss(None, (), None, (Gloss('la', (), None, ()),)), Gloss(None, ('v',), None, (Gloss(None, ('v',), None, ()), Gloss(None, (), 'PROG', ()),)))]}, 'plan': {'token': [('0', ('add', 'lookup')), ('return', 'unparsed')]}}

    def test_fullgloss_opt_spaces(self):
        fg = u':v: [::]'
        fg1 = u':v: [ :: ]'
        fg2 = u':v: [:: ]'
        fg3 = u':v: [ ::]'
        fg4 = u':v: [a:b:C]'
        fg5 = u':v: [ a:b:C ]'
        fg6 = u':v: [ a:b:C]'
        pg = Gloss(form=None, ps=(u'v',), gloss=None, morphemes=(Gloss(form=None, ps=(), gloss=None, morphemes=()),))
        pg1 = Gloss(form=None, ps=(u'v',), gloss=None, morphemes=(Gloss(form=u'a', ps=(u'b',), gloss=u'C', morphemes=()),))
        self.assertEquals(fullgloss_parser().parse(tokenize(fg)), pg) 
        self.assertEquals(fullgloss_parser().parse(tokenize(fg1)), pg) 
        self.assertEquals(fullgloss_parser().parse(tokenize(fg2)), pg) 
        self.assertEquals(fullgloss_parser().parse(tokenize(fg3)), pg) 
        self.assertEquals(fullgloss_parser().parse(tokenize(fg4)), pg1) 
        self.assertEquals(fullgloss_parser().parse(tokenize(fg5)), pg1) 
        self.assertEquals(fullgloss_parser().parse(tokenize(fg6)), pg1) 
        
    def test_parser(self):
        self.assertEquals(str(self.gmin), unicode(parse(tokenize(self.minimal))))
        self.assertEquals(str(self.greal), unicode(parse(tokenize(self.real))))

if __name__ == '__main__':
    unittest.main()
