#!/usr/bin/python
# -*- encoding: utf-8 -*-

import cPickle
import operator
import re
from contextlib import closing

def unwrap_re(string):
    unfolded = string.strip('{}').split('|')
    for i,part in enumerate(unfolded):
        if len(unfolded) > 1:
            if part:
                unfolded[i] = ur'({0})'.format(part.strip('<>'))
            else:
                unfolded[i] = r'(.+)'
        else:
            if part.startswith('<') and part.endswith('>'):
                return re.compile(part.strip('<>'))
            else:
                return part
    return re.compile(ur''.join(unfolded))

def match_any(self, other):
    try:
        return unwrap_re(other).search(self)
    except AttributeError:
        return self == other

def provide_morph(gloss):
    if not gloss.morphemes:
        temp = Gloss()
        temp[0] = gloss
        temp.morphemes = [gloss]
        return temp
    else:
        return gloss

class GlossError(Exception):
    def __init__(self, gstring):
        self.gstring = gstring

    def __str__(self):
        return repr(u'malformed gloss: {0}'.format(self.gstring))

class Gloss(object):
    def __init__(self, gstring = '::', morphemes = None):
        try:
            form, ps, gloss = gstring.split(':')
            self.form = form
            self.ps = ps and ps.split('/') or []
            self.gloss = gloss
            self.morphemes = morphemes or []
        except ValueError:
            raise GlossError(gstring)

    def __iter__(self):
        yield self
        if self.morphemes:
            for m in self.morphemes:
                yield m

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
        return all(i == j for i,j in zip(self,other))

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
        if self.ps or other.ps:
            if not other.ps:
                return True
            else:
                return bool(set(self.ps).intersection(set(other.ps)))
        else:
            return True

    def morphmatch(self, other, fuzzy=False):
        if self.morphemes or other.morphemes:
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
        else:
            return True

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
            return other
        smpattern = []
        shift = 0
        for sm in self.select.morphemes:
            for i,om in enumerate(target.morphemes):
                # FIXME: should match by whole morphemes pattern
                if om.matches(sm):
                    smpattern.append(i+shift)
                    if sm.form.startswith('{') and sm.form.endswith('}'):
                        splitter = unwrap_re(sm.form)
                        newmorphs = splitter.search(om.form).groups()
                        target.morphemes[i:i+1] = [Gloss(u':'.join([newform, '', ''])) for newform in newmorphs]
                        for m in newmorphs[1:]:
                            shift = shift + len(newmorphs)-1
                            smpattern.append(i+shift)
                # NB: search till the first match only
                break
        return target.union(self.mark, pattern=smpattern)


import unittest

class TestObjects(unittest.TestCase):
    
    def setUp(self):
        self.ga = Gloss(u'ab:n:gloss')
        self.gam = Gloss(u'ab:n:gloss', [Gloss(u'a:n:gloss'), Gloss(u'b:mrph:ge')])
        self.m = Gloss(u'::', [Gloss(u':n:'), Gloss(u'b:mrph:ge')])
        self.gre = Gloss(u'<.>:n:<g.*>')
        self.pat = Pattern(Gloss('::', [Gloss('{.|b}::')]), Gloss('::', [Gloss(':n:gloss'), Gloss(':mrph:ge')]))
        self.gm = Gloss(u'abw:n:gloss', [Gloss('ab::')])
        self.gmw = Gloss(u'abw:n:gloss', [Gloss('ab::'), Gloss('w::')])
        self.patm = Gloss('::', [Gloss('{.|b}::')])
        self.patmw = Gloss('::', [Gloss('{.|b}::'), Gloss('w::')])

    def test_gloss_general(self):
        # test gloss creation
        self.assertRaises(GlossError, Gloss, u'')
        # test gloss return value
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a:ps:gloss')))
        self.assertEquals(u'a:n/adj:gloss', unicode(Gloss(u'a:n/adj:gloss')))
        # test equality comparison
        #self.assertEquals(True, Gloss() == Gloss())
        #self.assertEquals(True, Gloss(u'a:n/adj:gloss') == Gloss(u'a:adj/n:gloss'))
        #self.assertEquals(False, Gloss(u'a:ps:gloss') == Gloss())
        #self.assertEquals(False, Gloss(u'a:n/adj:gloss') == Gloss(u'a:n:gloss'))
        #self.assertEquals("Gloss(u'::', [Gloss(u':n:'), Gloss(u'b:mrph:ge')])", repr(self.m))

    def test_gloss_psmatch(self):
        # test gloss psmatch
        self.assertEquals(True, Gloss().psmatch(Gloss(u'b::')))
        self.assertEquals(True, Gloss(u':n/adj:').psmatch(Gloss(u'b::')))
        self.assertEquals(True, Gloss(u':n:').psmatch(Gloss(u'b:n:')))
        self.assertEquals(True, Gloss(u':n:').psmatch(Gloss(u'b:n/adj:')))
        self.assertEquals(True, Gloss(u':n/adj:').psmatch(Gloss(u'b:n:')))
        self.assertEquals(True, Gloss(u':n/adj:').psmatch(Gloss(u':n/adj:')))
        self.assertEquals(False, Gloss().psmatch(Gloss(u':v:')))
        self.assertEquals(False, Gloss(u':n:').psmatch(Gloss(u':v:')))
        self.assertEquals(False, Gloss(u':n/adj:').psmatch(Gloss(u':v:')))
        self.assertEquals(False, Gloss(u':n/adj:').psmatch(Gloss(u':v:')))

    def test_gloss_morphmatch(self):
        self.assertEquals(True, Gloss().morphmatch(Gloss()))
        self.assertEquals(True, self.gam.morphmatch(self.m))
        self.assertEquals(True, self.gm.morphmatch(self.patm))
        self.assertEquals(True, self.gm.morphmatch(self.patm,fuzzy=True))
        self.assertEquals(True, self.gmw.morphmatch(self.patmw,fuzzy=True))
        self.assertEquals(False, self.gm.morphmatch(self.patmw,fuzzy=True))
        self.assertEquals(False, self.ga.morphmatch(self.gam))
        self.assertEquals(False, self.gam.morphmatch(self.ga))

    def test_gloss_matches(self):
        # test gloss pattern matching
        #NB: empty pattern matches any gloss
        self.assertEquals(True, Gloss().matches(Gloss()))
        self.assertEquals(True, Gloss(u'a:ps:gloss').matches(Gloss()))
        self.assertEquals(True, Gloss(u'a:ps:gloss').matches(Gloss(u'::gloss')))
        self.assertEquals(True, Gloss(u'a:n/adj:gloss').matches(Gloss(u'a:n:')))
        self.assertEquals(True, Gloss(u'a:n/adj:').matches(Gloss(u'a:n:')))
        self.assertEquals(False, Gloss().matches(Gloss(u'a::')))
        self.assertEquals(False, Gloss(u'a:ps:').matches(Gloss(u'::gloss')))
        self.assertEquals(False, Gloss(u'a:ps:gloss').matches(Gloss(u'b:ps:gloss')))
        self.assertEquals(False, Gloss(u'a:n/adj:gloss').matches(Gloss(u'b:n:')))
        self.assertEquals(False, Gloss(u'a:n/adj:gloss').matches(Gloss(u'b:v:')))
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
        self.assertEquals(unicode(self.gam), unicode(self.pat.apply(self.gam)))
        self.assertEquals(unicode(self.gam), unicode(self.pat.apply(self.ga)))


if __name__ == '__main__':
    unittest.main()
