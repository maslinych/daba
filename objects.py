#!/usr/bin/python
# -*- encoding: utf-8 -*-

import cPickle
import operator
import re
from contextlib import closing


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
        for i in self.form, set(self.ps), self.gloss:
            yield i

    def __eq__(self, other):
        return all(i == j for i,j in zip(self,other))

    def __unicode__(self):
        gstring = u':'.join([self.form,'/'.join(self.ps),self.gloss])
        if self.morphemes:
            return u'{0}, [{1}]'.format(gstring, u', '.join(unicode(g) for g in self.morphemes))
        else:
            return gstring

    def __repr__(self):
        gstring = 'Gloss({0})'.format(repr(unicode(self)))
        if self.morphemes:
            return '{0}, [{1}]'.format(gstring, ', '.join(repr(g) for g in self.morphemes))
        else:
            return gstring

    def psmatch(self, other):
        if self.ps or other.ps:
            if not other.ps:
                return True
            else:
                return bool(set(self.ps).intersection(set(other.ps)))
        else:
            return True

    def morphmatch(self, other):
        if self.morphemes or other.morphemes:
            if len(self.morphemes) == len(other.morphemes):
                return all([s.matches(o) for s,o in zip(self.morphemes,other.morphemes)])
            else:
                return False
        else:
            return True

    def matches(self,other):
        'pattern matching device: feature comparison function'
        if other.form and re.search(other.form, self.form) or not other.form:
            if other.gloss and self.gloss == other.gloss or not other.gloss:
                if self.psmatch(other):
                    return self.morphmatch(other)
        return False

    def union(self, other):
        if other.form and re.search(other.form, self.form) or not other.form:
            if self.psmatch(other):
                if other.gloss and self.gloss != other.gloss:
                    self.gloss = other.gloss
                if self.ps and other.ps:
                    self.ps = list(set(self.ps).intersection(set(other.ps)))
                else:
                    self.ps = list(set(self.ps).union(set(other.ps)))
                if other.morphemes: 
                    if not self.morphemes:
                        self.morphemes = other.morphemes
                    else:
                        self.morphemes = [s.union(o) for s,o in zip(self.morphemes,other.morphemes)]
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

import unittest

class TestGlossObjects(unittest.TestCase):
    
    def setUp(self):
        self.ga = Gloss(u'a:n:gloss')
        self.gam = Gloss(u'ab:n:gloss', [Gloss(u'a:n:gloss'), Gloss(u'b:mrph:ge')])
        self.m = Gloss(u'::', [Gloss(u':n:'), Gloss(u'b:mrph:ge')])

    def test_gloss_general(self):
        # test gloss creation
        self.assertRaises(GlossError, Gloss, u'')
        # test gloss return value
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a:ps:gloss')))
        self.assertEquals(u'a:n/adj:gloss', unicode(Gloss(u'a:n/adj:gloss')))
        self.assertEquals((u'a',set(['ps']),u'gloss'), tuple(i for i in Gloss(u'a:ps:gloss')))
        # test equality comparison
        self.assertEquals(True, Gloss() == Gloss())
        self.assertEquals(True, Gloss(u'a:n/adj:gloss') == Gloss(u'a:adj/n:gloss'))
        self.assertEquals(False, Gloss(u'a:ps:gloss') == Gloss())
        self.assertEquals(False, Gloss(u'a:n/adj:gloss') == Gloss(u'a:n:gloss'))

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

    def test_gloss_union(self):
        # test gloss union (typical use: union with pattern data)
        # NB: empty gloss always returns empty union
        self.assertEquals(u'::', unicode(Gloss().union(Gloss())))
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a:ps:gloss').union(Gloss())))
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a:n/adj:gloss').union(Gloss(u'a:n:'))))
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a:ps:').union(Gloss(u'::gloss'))))
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a:n/adj:').union(Gloss(u':n:gloss'))))
        self.assertEquals(u'::', unicode(Gloss().union(Gloss(u'a::'))))
        self.assertEquals(u'::', unicode(Gloss(u'a:ps:gloss').union(Gloss(u'b:ps:gloss'))))
        self.assertEquals(u'::', unicode(Gloss(u'a:n/adj:gloss').union(Gloss(u'b:n:'))))
        self.assertEquals(u'::', unicode(Gloss(u'a:n/adj:gloss').union(Gloss(u'b:v:'))))
        self.assertEquals(u'ab:n:gloss, [a:n:gloss, b:mrph:ge]', unicode(self.gam.union(self.ga)))
        self.assertEquals(u'ab:n:gloss, [a:n:gloss, b:mrph:ge]', unicode(self.gam.union(self.m)))


if __name__ == '__main__':
    unittest.main()
