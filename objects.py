#!/usr/bin/python
# -*- encoding: utf-8 -*-

import cPickle
import operator
import re
import itertools
import copy
from contextlib import closing
from funcparserlib.parser import *
from funcparserlib.lexer import make_tokenizer, Token, LexerError

def unwrap_re(string):
    def tokenize(string):
        specs = [
                ('Regex', (r'<re>.+?</re>', re.UNICODE)),
                ('String', (r"[^<{|}>:][^<{|}>:]*", re.UNICODE)),
                ('Op', (r'[|{}]',)),
                ]
        tok = make_tokenizer(specs)
        return [t for t in tok(string)]

    def parse(seq):
        tokval = lambda x: x.value
        unfoldl = lambda l: [j for i in l for j in i]
        foldl = lambda s: [s]
        string = some(lambda t: t.type == 'String') >> tokval
        regex = some(lambda t: t.type == 'Regex') >> tokval
        op = lambda s: a(Token('Op', s)) >> tokval
        op_ = lambda s: skip(op(s))
        re_or_string = regex | string
        splitter = oneplus(op_('|') + maybe(re_or_string))
        starter = maybe(re_or_string) >> foldl
        split_expr = op_('{') + starter + splitter + op_('}') >> unfoldl
        form = split_expr | starter + skip(finished)
        return form.parse(seq)

    unfolded = parse(tokenize(string))
    for i,part in enumerate(unfolded):
        if len(unfolded) > 1:
            if part:
                if part.startswith('<re>') and part.endswith('</re>'):
                    part = part[4:-5]
                unfolded[i] = ur'(?P<__group{0}>{1})'.format(i,part)
            else:
                unfolded[i] = r'(?P<__group{0}>.+)'.format(i)
        else:
            if part.startswith('<re>') and part.endswith('</re>'):
                return re.compile(part[4:-5])
            else:
                return part
    # FIXME: degug comment
    #print ''.join(unfolded)
    return re.compile(ur'^{0}$'.format(''.join(unfolded)))

def match_any(self, other):
    try:
        return unwrap_re(other).search(self)
    except AttributeError:
        return self == other

def provide_morph(gloss):
    temp = Gloss()
    temp.form = gloss.form
    temp.ps = copy.deepcopy(gloss.ps)
    temp.gloss = gloss.gloss
    if not gloss.morphemes:
        temp.morphemes = [copy.deepcopy(gloss)]
    else:
        temp.morphemes = copy.deepcopy(gloss.morphemes)
    return temp

class GlossError(Exception):
    def __init__(self, gstring):
        self.gstring = gstring

    def __str__(self):
        return repr(u'malformed gloss: {0}'.format(self.gstring))

class Gloss(object):
    def __init__(self, gstring = '::', morphemes = None):
        def tokenize(string):
            specs = [
                    ('Regex', (r'({.+}|<re>.+?</re>)', re.UNICODE)),
                    ('Op', (r':',)),
                    ('String', (r"[^<{|}>:][^<{|}>:]*", re.UNICODE)),
                    ]
            tok = make_tokenizer(specs)
            return [t for t in tok(string)]
    
        def parse(seq):
            tokval = lambda x: x.value
            unfoldl = lambda l: [j for i in l for j in i]
            foldl = lambda s: [s]
            string = some(lambda t: t.type == 'String') >> tokval
            regex = some(lambda t: t.type == 'Regex') >> tokval
            op = lambda s: a(Token('Op', s)) >> tokval
            op_ = lambda s: skip(op(s))
            re_or_string = maybe(regex | string)
            form = re_or_string + op_(':') + re_or_string + op_(':') + re_or_string + skip(finished)
            return form.parse(seq)

        try:
            form, ps, gloss = parse(tokenize(gstring))
        except (NoParseError, LexerError, ValueError):
            raise GlossError(gstring)

        self.form = form or ''
        self.ps = ps and ps.split('/') or []
        self.gloss = gloss or ''
        self.morphemes = morphemes or []

    def __iter__(self):
        yield self
        if self.morphemes:
            for m in self.morphemes:
                yield m

    def __len__(self):
        return len([i for i in self])

    def __getitem__(self, index):
        for i,g in enumerate(self):
            if i == int(index):
                return g
    
    def __setitem__(self, index, other):
        for i,g in enumerate(self):
            if i == int(index):
                for k in g.__dict__:
                    g.__dict__[k] = other.__dict__[k]

    def __eq__(self, other):
        def glosseq(i,j):
            return i.form == j.form and set(i.ps) == set(j.ps) and i.gloss == j.gloss
        return all(glosseq(i,j) for i,j in zip(self,other))

    def __unicode__(self):
        gstring = u':'.join([self.form,'/'.join(self.ps),self.gloss])
        if self.morphemes:
            return u'{0}, [{1}]'.format(gstring, u', '.join(unicode(g) for g in self.morphemes))
        else:
            return gstring

    def __repr__(self):
        gstring = u':'.join([self.form,'/'.join(self.ps),self.gloss])
        if self.morphemes:
            return 'Gloss({0}, [{1}])'.format(repr(gstring), ', '.join(repr(g) for g in self.morphemes))
        else:
            return 'Gloss({0})'.format(repr(gstring))

    def psmatch(self, other):
        if self.ps and other.ps:
            return bool(set(self.ps).intersection(set(other.ps)))
        else:
            return True

    def morphmatch(self, other, fuzzy=False):
        if self.morphemes and other.morphemes:
            if not fuzzy:
                if len(self.morphemes) == len(other.morphemes):
                    return all([s.matches(o) for s,o in zip(self.morphemes,other.morphemes)])
                else:
                    return False
            # doing fuzzy match
            else:
                if len(self.morphemes) < len(other.morphemes):
                    return False
                else:
                    for i,sm in enumerate(self.morphemes):
                        if sm.matches(other.morphemes[0]):
                            otail = other.morphemes[1:]
                            stail =  self.morphemes[i+1:]
                            if len(stail) < len(otail):
                                return False
                            else:
                               return all(s.matches(o) for s,o in zip(stail, otail))
                    return False
        elif not other.morphemes:
            return True
        else:
            return False

    def matches(self,other,fuzzy=False):
        'pattern matching device: feature comparison function'
        if other.form and match_any(self.form, other.form) or not other.form:
            if other.gloss and match_any(self.gloss, other.gloss) or not other.gloss:
                if self.psmatch(other):
                    return self.morphmatch(other,fuzzy)
        return False

    def union(self, other, pattern=None):
        if self.form or self.ps or self.gloss:
        #if other.form and match_any(self.form, other.form) or not other.form:
            #if self.psmatch(other):
                if self.ps and other.ps:
                    common = list(set(self.ps).intersection(set(other.ps)))
                    if not common:
                        return Gloss()
                    else:
                        self.ps = common
                else:
                    self.ps = list(set(self.ps).union(set(other.ps)))
                if other.gloss and not match_any(self.gloss, other.gloss):
                    self.gloss = other.gloss
                if other.form and not match_any(self.form, other.form):
                    self.form = other.form
                if other.morphemes: 
                    if not self.morphemes:
                        self.morphemes = other.morphemes
                    else:
                        if not pattern:
                            self.morphemes = [s.union(o) for s,o in zip(self.morphemes,other.morphemes)]
                        else:
                            # doing union by pattern
                            for i,o in zip(pattern, other.morphemes):
                                self.morphemes[i].union(o)
                return self
        else:
            return Gloss()


class CompactGloss(Gloss):
    'self.morphemes :: [[Gloss]]'
    def __init__(self, base=None, *args):
        if not base:
            base = Gloss(*args)
        self.form = base.form
        self.ps = copy.deepcopy(base.ps)
        self.gloss = base.gloss
        self.morphemes = copy.deepcopy(base.morphemes)

    def __iter__(self):
        yield self
        if self.morphemes:
            for m in self.morphemes:
                if isinstance(m, list):
                    for i in m:
                        yield i
                else:
                    yield m

    def to_glosslist(self):
        'CompactGloss -> [Gloss]'
        result = []
        for mset in itertools.product(*self.morphemes):
            new = Gloss()
            new[0] = self[0]
            # FIXME: don't forget to change to tuple when needed
            new.morphemes = list(mset)
            result.append(new)
        return result


class Dictionary(object):
    def __init__(self, filename=None):
        if not filename:
            self.lexicon = {}
        else:
            with closing(open(filename, 'rb')) as dictfile:
                self.lexicon = cPickle.load(dictfile)

    def __contains__(self,item):
        return item in self.lexicon

    def __getitem__(self,item):
        return self.lexicon[item]

    def __len__(self):
        return len(self.lexicon)

class Pattern(object):
    def __init__(self, select, mark):
        self.select = select
        self.mark = mark

    def __repr__(self):
        return 'Pattern({0}, {1})'.format(repr(self.select),repr(self.mark))

    def __eq__(self, other):
        return self.select == other.select and self.mark == other.mark

    def matches(self, other, fuzzy=True):
        # NB: fuzzy match by default
        return provide_morph(other).matches(self.select,fuzzy)

    def apply(self, other):
        # NB: operates by side efect!
        target = provide_morph(other)
        if not self.matches(target):
            return None
        smpattern = []
        shift = 0
        for sm in self.select.morphemes:
            for i,om in enumerate(target.morphemes):
                # FIXME: should match by whole morphemes pattern
                if om.matches(sm):
                    smpattern.append(i+shift)
                    if sm.form.startswith('{') and sm.form.endswith('}'):
                        splitter = unwrap_re(sm.form)
                        newmorphs = filter(lambda x: x[0].startswith('__group'), splitter.search(om.form).groupdict().items())
                        newmorphs.sort()
                        newmorphs = list(zip(*newmorphs)[1])
                        target.morphemes[i:i+1] = [Gloss(u':'.join([newform, '', ''])) for newform in newmorphs]
                        for m in newmorphs[1:]:
                            shift += 1
                            smpattern.append(i+shift)
                # NB: search till the first match only
                break
        # FIXME: should I fix union logic to return None if no psmatch?
        union = target.union(self.mark, pattern=smpattern)
        if union == Gloss():
            return None
        else:
            return union


import unittest

class TestObjects(unittest.TestCase):
    
    def setUp(self):
        self.ga = Gloss(u'ab:n:gloss')
        self.gam = Gloss(u'ab:n:gloss', [Gloss(u'a:n:gloss'), Gloss(u'b:mrph:ge')])
        self.m = Gloss(u'::', [Gloss(u':n:'), Gloss(u'b:mrph:ge')])
        self.gre = Gloss(u'<re>.</re>:n:<re>g.*</re>')
        self.pat = Pattern(Gloss('::', [Gloss('{<re>.</re>|b}::')]), Gloss('::', [Gloss(':n:gloss'), Gloss(':mrph:ge')]))
        self.gm = Gloss(u'abw:n:gloss', [Gloss('ab::')])
        self.gmw = Gloss(u'abw:n:gloss', [Gloss('ab::'), Gloss('w::')])
        self.patm = Gloss('::', [Gloss('{<re>.</re>|b}::')])
        self.patmw = Gloss('::', [Gloss('{<re>.</re>|b}::'), Gloss('w::')])

    def test_gloss_general(self):
        # test gloss creation
        self.assertRaises(GlossError, Gloss, u'')
        # test gloss return value
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a:ps:gloss')))
        self.assertEquals(u'a:n/adj:gloss', unicode(Gloss(u'a:n/adj:gloss')))
        # test equality comparison
        self.assertEquals(True, Gloss() == Gloss())
        self.assertEquals(True, Gloss(u'a:n/adj:gloss') == Gloss(u'a:adj/n:gloss'))
        self.assertEquals(False, Gloss(u'a:ps:gloss') == Gloss())
        self.assertEquals(False, Gloss(u'a:n/adj:gloss') == Gloss(u'a:n:gloss'))
        self.assertEquals("Gloss(u'::', [Gloss(u':n:'), Gloss(u'b:mrph:ge')])", repr(self.m))

    def test_gloss_psmatch(self):
        # test gloss psmatch
        # synopsis: PATTERN.psmatch(FORM)
        self.assertEquals(True, Gloss().psmatch(Gloss(u'b::')))
        self.assertEquals(True, Gloss().psmatch(Gloss(u':v:')))
        self.assertEquals(True, Gloss(u':n/adj:').psmatch(Gloss(u'b::')))
        self.assertEquals(True, Gloss(u':n:').psmatch(Gloss(u'b:n:')))
        self.assertEquals(True, Gloss(u':n:').psmatch(Gloss(u'b:n/adj:')))
        self.assertEquals(True, Gloss(u':n/adj:').psmatch(Gloss(u'b:n:')))
        self.assertEquals(True, Gloss(u':n/adj:').psmatch(Gloss(u':n/adj:')))
        self.assertEquals(False, Gloss(u':n:').psmatch(Gloss(u':v:')))
        self.assertEquals(False, Gloss(u':n/adj:').psmatch(Gloss(u':v:')))
        self.assertEquals(False, Gloss(u':n/adj:').psmatch(Gloss(u':v:')))

    def test_gloss_morphmatch(self):
        self.assertEquals(True, Gloss().morphmatch(Gloss()))
        self.assertEquals(True, self.gam.morphmatch(self.m))
        self.assertEquals(True, self.gm.morphmatch(self.patm))
        self.assertEquals(True, self.gm.morphmatch(self.patm,fuzzy=True))
        self.assertEquals(True, self.gmw.morphmatch(self.patmw,fuzzy=True))
        self.assertEquals(True, self.gam.morphmatch(self.ga))
        self.assertEquals(False, self.ga.morphmatch(self.gam))
        self.assertEquals(False, self.gm.morphmatch(self.patmw,fuzzy=True))

    def test_gloss_matches(self):
        # test gloss pattern matching
        # synopsis: FORM.matches(PATTERN)
        #NB: empty pattern matches any gloss
        self.assertEquals(True, Gloss().matches(Gloss()))
        self.assertEquals(True, Gloss(u'a:ps:gloss').matches(Gloss()))
        self.assertEquals(True, self.gam.matches(Gloss()))
        self.assertEquals(True, Gloss(u'a:ps:gloss').matches(Gloss(u'::gloss')))
        self.assertEquals(True, Gloss(u'a:n/adj:gloss').matches(Gloss(u'a:n:')))
        self.assertEquals(True, Gloss(u'a:n/adj:').matches(Gloss(u'a:n:')))
        self.assertEquals(False, Gloss().matches(Gloss(u'a::')))
        self.assertEquals(False, Gloss(u'a:ps:').matches(Gloss(u'::gloss')))
        self.assertEquals(False, Gloss(u'a:ps:gloss').matches(Gloss(u'b:ps:gloss')))
        self.assertEquals(False, Gloss(u'a:n/adj:gloss').matches(Gloss(u'b:n:')))
        self.assertEquals(False, Gloss(u'a:n/adj:gloss').matches(Gloss(u'b:v:')))
        self.assertEquals(False, Gloss(u'sira:n:gloss').matches(Gloss(u':v:')))
        self.assertEquals(False, Gloss(u'w::').matches(Gloss(u'w:mrph:PL')))
        # test regex capabilities
        self.assertEquals(True, Gloss(u'a:n:gloss').matches(self.gre))
        self.assertEquals(True, Gloss(u'b:n:ge').matches(self.gre))
        self.assertEquals(False, Gloss().matches(self.gre))

    def test_gloss_union(self):
        # test gloss union (typical use: union with pattern data)
        # NB: empty gloss always returns empty union
        self.assertEquals(u'::', unicode(Gloss().union(Gloss())))
        self.assertEquals(u'á:ps:gloss', unicode(Gloss(u'a::').union(Gloss(u'á:ps:gloss'))))
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a:ps:gloss').union(Gloss())))
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a:n/adj:gloss').union(Gloss(u'a:n:'))))
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a:ps:').union(Gloss(u'::gloss'))))
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a:n/adj:').union(Gloss(u':n:gloss'))))
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a::').union(Gloss(u':n:gloss'))))
        self.assertEquals(u'::', unicode(Gloss().union(Gloss(u'a::'))))
        self.assertEquals(u'b:n:gloss', unicode(Gloss(u'a:n/adj:gloss').union(Gloss(u'b:n:'))))
        self.assertEquals(u'::', unicode(Gloss(u'a:n/adj:gloss').union(Gloss(u'b:v:'))))
        self.assertEquals(u'ab:n:gloss, [a:n:gloss, b:mrph:ge]', unicode(self.gam.union(self.ga)))
        self.assertEquals(u'ab:n:gloss, [a:n:gloss, b:mrph:ge]', unicode(self.gam.union(self.m)))
        # test morphemes union by pattern
        self.assertEquals(u'ab::, [a::1, b::2]', unicode(Gloss('ab::', [Gloss('a::'), Gloss('b::')]).union(Gloss('::', [Gloss('::2'), Gloss('::1')]), pattern=(1,0))))
        # test regex capabilities
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a:n:gloss').union(self.gre)))

    def test_pattern(self):
        self.assertEquals(True, self.pat.matches(self.ga))
        self.assertEquals(False, self.pat.matches(self.gam))
        self.assertEquals(unicode(self.gam), unicode(self.pat.apply(self.ga)))


if __name__ == '__main__':
    unittest.main()
