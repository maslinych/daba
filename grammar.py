#!/usr/bin/python
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
            ('Space', (r'[ \t\r\n]+',)),
            ('Op', (r'[\[\]|:{}]',)),
            #('Regex', (r'<(\w|[-={}\[\]|().,^$+*?:\\])*>', re.UNICODE)),
            ('Regex', (r'<re>.*?</re>', re.UNICODE)),
            ('Name', (ur'[^:<>\[\]{}| \n]+', re.UNICODE)),
            #('Name', (ur"(\w[\u0300\u0301\u0302]?)+([-./](\w[\u0300\u0301\u0302]?)+)*['\u2019]?",re.UNICODE)),
            #('Name', (ur'(\w[\u0300\u0301]?([-./](\w[\u0300\u0301]?)+)*|[-0-9][-0-9]*)',re.UNICODE))
            ]
    useless = ['Comment', 'NL', 'Space']
    tok = make_tokenizer(specs)
    return [x for x in tok(string) if x.type not in useless]

def unwrap_re(tupl):
    unre = lambda s: s[4:-5]
    if not isinstance(tupl, tuple):
        return re.compile(ur'^(?P<__group0>{0})$'.format(unre(tupl)))
    unfolded = []
    for i,part in enumerate(tupl):
        # FIXME: to be done by formparser
        #if part.startswith(('') and part.endswith('',)):
        #    part = part[4:-5]
        if not part:
            part = '.+'
        elif part.startswith('<re>'):
            part = unre(part)
        unfolded.append(ur'(?P<__group{0}>{1})'.format(i,part))
    return re.compile(ur'^{0}$'.format(''.join(unfolded)))

tokval = lambda x: x.value
name = some(lambda t: t.type == 'Name') >> tokval
pslabel = some(lambda t: t.value in PSLIST) >> tokval
space = some(lambda t: t.type == 'Space') >> tokval
op = lambda s: a(Token('Op', s)) >> tokval
op_ = lambda s: skip(op(s))
foldl = lambda s: [s]
unfoldl = lambda l: [k for j in [i for i in l if i] for k in j]
unarg = lambda f: lambda args: f(*args)
joinif = lambda x: ''.join(i for i in x if i)
denone = lambda s: s or ()
makeset = lambda s: set(s.split('/')) if s else set([])
denoneset = lambda s: s or set()
filternone = lambda s: [i for i in s if i]

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
            ('Name', (ur'[^:/ \[\]\r\t\n]+', re.UNICODE)),
            ]
    useless = ['JunkSpace']
    tok = make_tokenizer(specs)
    return [x for x in tok(string) if x.type not in useless]

def stringgloss_parser():
    ps = pslabel + maybe(many(op_('/') + pslabel)) >> flatten_list >> set
    lemma = name + op_(':') + ( maybe(ps) >> denoneset ) + op_(':') + maybe(name) 
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
    lemma = maybe(form_expr | unregex | name ) + op_(':') + (maybe(name) >> makeset ) + op_(':') + maybe(name | unregex) 
    fullgloss = forward_decl()
    glosslist = skip(op('[')) + many(fullgloss) + skip(op(']')) >> tuple
    fullgloss.define(lemma + ( maybe(glosslist) >> denone ) >> unarg(Gloss))

    return fullgloss


def parse(seq):
    'Sequence(Token) -> grammar dict'
    make_patterns = lambda x: ('patterns', x)
    n = lambda s: a(Token('Name', s)) >> tokval
    # plan syntax
    f_add = n('add') 
    f_apply = n('apply') 
    f_lookup = n('lookup') 
    f_parallel = n('parallel') 
    f_sequential = n('sequential') 
    f_firstmatch = n('firstmatch')
    f_parse = n('parse') + name >> list
    f_decompose = n('decompose') + name >> list
    func_clause = oneplus(f_add | f_apply | f_lookup | f_parallel | f_sequential | f_firstmatch) + maybe(f_parse | f_decompose) >> unfoldl >> tuple
    stage_clause = skip(n('stage')) + name + func_clause 
    return_clause = n('return') + skip(n('if')) + name
    for_clause = skip(n('for')) + name + skip(op(':')) + many(stage_clause | return_clause ) >> tuple
    plan_dict = oneplus(for_clause) >> dict
    plan = n('plan') + plan_dict  >> tuple
    # pattern syntax
    pattern = skip(n('pattern')) + fullgloss_parser() + skip(op('|')) + fullgloss_parser() >> unarg(Pattern)
    sec_header = skip(n('section')) + name 
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
        with open(filename, 'r') as gf:
            text = preprocess(gf.read().decode(encoding))
            gdict = parse(tokenize(text))
            self.plan = gdict['plan']
            self.patterns = gdict['patterns']

import unittest

# FIXME: TESTS WITH OBSOLETE GLOSS SYNTAX
class TestGrammarParser(unittest.TestCase):

    def setUp(self):
        self.minimal = 'plan for token: stage 0 add lookup section n pattern :: | ::'
        self.gmin = {'patterns': {'n': [Pattern(Gloss(u'::'), Gloss(u'::'))]}, 'plan': {'token': [('0', ('add', 'lookup'))]}}
        self.real = """
        plan for token: stage 0 add lookup
        return if unparsed
        # some comment
        section n
        pattern :: [ {<re>[^n]$</re>|la}::] | :v: [:v: ::PROG]
        """
        self.greal = {'patterns': {'n': [Pattern(Gloss(u'::', [Gloss(u'{<re>[^n]$</re>|la}::')]), Gloss(u':v:', [Gloss(u':v:'), Gloss(u'::PROG')]))]}, 'plan': {'token': [('0', ('add', 'lookup')), ('return', 'unparsed')]}}

    def test_parser(self):
        self.assertEquals(unicode(self.gmin), unicode(parse(tokenize(self.minimal))))
        self.assertEquals(unicode(self.greal), unicode(parse(tokenize(self.real))))

if __name__ == '__main__':
    unittest.main()
