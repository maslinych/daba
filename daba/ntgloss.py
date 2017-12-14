#/usr/bin/python
# -*- coding: utf-8 -*-

from collections import namedtuple
from contextlib import closing
import re
import cPickle
import itertools
import xml.etree.cElementTree as e

unfold = lambda l: [j for i in l for j in i]

def unwrap_re(tupl):
    if not isinstance(tupl, tuple):
        raise GlossError('not a regexp: {0}'.format(tupl))
    unfolded = []
    for i,part in enumerate(tupl):
        # FIXME: to be done by formparser
        #if part.startswith(('') and part.endswith('',)):
        #    part = part[4:-5]
        if not part:
            part = '.+'
        unfolded.append(ur'(?P<__group{0}>{1})'.format(i,part))
    return re.compile(ur'^{0}$'.format(''.join(unfolded)))

def match_any(my, other):
    try:
        return bool(other.search(my))
    except AttributeError:
        return my == other

def provide_morph(gloss):
    if not gloss.morphemes:
        return gloss._replace(morphemes = (gloss,))
    else:
        return gloss

class GlossError(Exception):
    def __init__(self, gstring):
        self.gstring = gstring

    def __str__(self):
        return repr(self.gstring)

class Gloss(namedtuple('Gloss', 'form ps gloss morphemes')):
    __slots__ = ()

    def itermorphs(self):
        yield self
        if self.morphemes:
            for m in self.morphemes:
                yield m
    
    def __unicode__(self):
        def untuple(f):
            try:
                return f.pattern
            except AttributeError:
                return f
        form = untuple(self.form)
        gloss = untuple(self.gloss)
        gstring = u':'.join([i if i else '' for i in [form,'/'.join(self.ps),gloss]])
        if self.morphemes:
            return u'{0} [{1}]'.format(gstring, u' '.join(unicode(g) if g else '' for g in self.morphemes))
        else:
            return gstring
   
    def psmatch(self, other, strict=False):
        if strict:
            return self.ps == other.ps
        elif self.ps and other.ps:
            return bool(set(self.ps) & set(other.ps))
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

    def matches(self, other, fuzzy=False, psstrict=False):
        'pattern matching device: feature comparison function'
        if other.form and match_any(self.form, other.form) or not other.form:
            if other.gloss and match_any(self.gloss, other.gloss) or not other.gloss:
                if self.psmatch(other, strict=psstrict):
                    return self.morphmatch(other,fuzzy)
        return False
    
    def psunion(self, otherps):
        if self.ps and otherps:
            ps = [tag for tag in self.ps if tag in otherps]
            if not ps:
                raise ValueError
        else:
            ps = []
            for tag in self.ps + otherps:
                if tag not in ps:
                    ps.append(tag)
        return tuple(ps)

    def union(self, other, pattern=None, psoverride=False):
        if self.form or self.ps or self.gloss:
        #if other.form and match_any(self.form, other.form) or not other.form:
            #if self.psmatch(other):
                if psoverride:
                    self = self._replace(ps = other.ps)
                else:
                    try:
                        self = self._replace(ps = self.psunion(other.ps))
                    except (ValueError):
                        return None
                if other.gloss and not match_any(self.gloss, other.gloss):
                    self = self._replace(gloss = other.gloss)
                if other.form and not match_any(self.form, other.form):
                    self = self._replace(form = other.form)
                if other.morphemes: 
                    if not self.morphemes:
                        self = self._replace(morphemes = other.morphemes)
                    else:
                        if not pattern:
                            self = self._replace(morphemes = tuple(s.union(o, psoverride=psoverride) for s,o in zip(self.morphemes,other.morphemes)))
                        else:
                            # doing union by pattern
                            patterndict = dict(zip(pattern, other.morphemes))
                            self = self._replace(morphemes = tuple(m.union(patterndict[i]) if i in patterndict else m for i,m in enumerate(self.morphemes)))
                return self
        else:
            return None

    def html(self, spanclass='w', variant=False):
        if variant:
            spanclass = 'lemma var'

        w = e.Element('span', {'class': spanclass})
        
        w.text = self.form
        ps = e.SubElement(w, 'sub', {'class': 'ps'})
        ps.text = '/'.join(self.ps) or '<?>'
        gloss = e.SubElement(w, 'sub', {'class':'gloss'})
        gloss.text = self.gloss or '<?>'

        for m in self.morphemes:
            #NB: SIDE EFFECT!
            w.append(m.html(spanclass='m'))
        return w


emptyGloss = Gloss('',(),'',())

class Pattern(object):
    def __init__(self, select, mark):
        self.select = select
        self.mark = mark
        self.splitterdict = {}
        for i,sm in enumerate(self.select.morphemes):
            try:
                #FIXME: instead of proper checking for regexp
                if sm.form.pattern:
                    self.splitterdict[i] = sm.form
            except AttributeError:
                pass

    def __repr__(self):
        return 'Pattern({0}, {1})'.format(repr(self.select), repr(self.mark))

    def matches(self, other, fuzzy=True):
        # NB: fuzzy match by default
        return provide_morph(other).matches(self.select,fuzzy)

    def apply(self, other):
        if self.select.morphemes:
            target = provide_morph(other)
        else:
            target = other
        if not self.matches(target):
            return None

        smpattern = []
        if self.select.morphemes:
            shift = 0
            for k,sm in enumerate(self.select.morphemes):
                for i,om in enumerate(target.morphemes):
                    # FIXME: should match by whole morphemes pattern
                    if om.matches(sm):
                        smpattern.append(i+shift)
                        if k in self.splitterdict: 
                            newmorphs = filter(lambda x: x[0].startswith('__group'), self.splitterdict[k].search(om.form).groupdict().items())
                            newmorphs.sort()
                            try:
                                newmorphs = list(zip(*newmorphs)[1])
                            except IndexError:
                                #FIXME: should not happen, add proper error handling
                                print "Error matching pattern:", newmorphs
                            target = target._replace(morphemes = tuple(unfold([[emptyGloss._replace(form=newform) for newform in newmorphs] if j==i else [tm] for j,tm in enumerate(target.morphemes)])))
                            for m in newmorphs[1:]:
                                shift += 1
                                smpattern.append(i+shift)
                        # NB: search till the first match only
                        break

        return target.union(self.mark, pattern=smpattern)

class CompactGloss(Gloss):
    __slots__ =()

    @property
    def glosslist(self):
        newmorphs = [tuple([t]) if isinstance(t, Gloss) else t for t in self.morphemes]
        return tuple([self._replace(morphemes=mset) for mset in itertools.product(*newmorphs)])

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

class TestObjects(unittest.TestCase):
    
    def setUp(self):
        self.ga = Gloss(u'ab',tuple(['n']),'gloss',())
        self.gam = Gloss(u'ab',tuple(['n']),'gloss', (Gloss(u'a',tuple(['n']),'gloss',()), Gloss(u'b',tuple(['mrph']),'ge',())))
        self.m = Gloss(u'',tuple([]),'', (Gloss(u'',tuple(['n']),'',()), Gloss(u'b',tuple(['mrph']),'ge',())))
        self.gre = Gloss(('.',),tuple(['n']),('g.*',),())
        self.pat = Pattern(Gloss('',tuple([]),'', (Gloss(('.', 'b'),'','',()),)), Gloss('',tuple([]),'', (Gloss('',tuple(['n']),'gloss',()), Gloss('',tuple(['mrph']),'ge',()),)))
        self.gm = Gloss(u'abw',tuple(['n']),'gloss', (Gloss('ab',tuple([]),'',()),))
        self.gmw = Gloss(u'abw',tuple(['n']),'gloss', (Gloss('ab',tuple([]),'',()), Gloss('w',tuple([]),'',()),))
        self.patm = Gloss('',tuple([]),'', (Gloss(('.', 'b'),'','',()),))
        self.patmw = Gloss('',tuple([]),'', (Gloss(('.', 'b'),'','',()), Gloss('w',tuple([]),'',())))

    def test_gloss_general(self):
        # test gloss creation
        #self.assertRaises(GlossError, Gloss, u'')
        # test gloss return value
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a',tuple(['ps']),'gloss',())))
        self.assertEquals(u'a:adj/n:gloss', unicode(Gloss(u'a',tuple(['n','adj']),'gloss',())))
        # test equality comparison
        self.assertEquals(True, emptyGloss == emptyGloss)
        self.assertEquals(True, Gloss(u'a',tuple(['n','adj']),'gloss',()) == Gloss(u'a',tuple(['adj','n']),'gloss',()))
        self.assertEquals(False, Gloss(u'a',tuple(['ps']),'gloss',()) == emptyGloss)
        self.assertEquals(False, Gloss(u'a',tuple(['n','adj']),'gloss',()) == Gloss(u'a',tuple(['n']),'gloss',()))
        #self.assertEquals("Gloss(u'',tuple([]),'', (Gloss(u'',tuple(['n']),'',()), Gloss(u'b',tuple(['mrph']),'ge',())))", repr(self.m))

    def test_gloss_psmatch(self):
        # test gloss psmatch
        # synopsis: PATTERN.psmatch(FORM)
        self.assertEquals(True, emptyGloss.psmatch(Gloss(u'b',tuple([]),'',())))
        self.assertEquals(True, emptyGloss.psmatch(Gloss(u'',tuple(['v']),'',())))
        self.assertEquals(True, Gloss(u'',tuple(['n','adj']),'',()).psmatch(Gloss(u'b',tuple([]),'',())))
        self.assertEquals(True, Gloss(u'',tuple(['n']),'',()).psmatch(Gloss(u'b',tuple(['n']),'',())))
        self.assertEquals(True, Gloss(u'',tuple(['n']),'',()).psmatch(Gloss(u'b',tuple(['n','adj']),'',())))
        self.assertEquals(True, Gloss(u'',tuple(['n','adj']),'',()).psmatch(Gloss(u'b',tuple(['n']),'',())))
        self.assertEquals(True, Gloss(u'',tuple(['n','adj']),'',()).psmatch(Gloss(u'',tuple(['n','adj']),'',())))
        self.assertEquals(False, Gloss(u'',tuple(['n']),'',()).psmatch(Gloss(u'',tuple(['v']),'',())))
        self.assertEquals(False, Gloss(u'',tuple(['n','adj']),'',()).psmatch(Gloss(u'',tuple(['v']),'',())))
        self.assertEquals(False, Gloss(u'',tuple(['n','adj']),'',()).psmatch(Gloss(u'',tuple(['v']),'',())))

    def test_gloss_morphmatch(self):
        self.assertEquals(True, emptyGloss.morphmatch(emptyGloss))
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
        self.assertEquals(True, emptyGloss.matches(emptyGloss))
        self.assertEquals(True, Gloss(u'a',tuple(['ps']),'gloss',()).matches(emptyGloss))
        self.assertEquals(True, self.gam.matches(emptyGloss))
        self.assertEquals(True, Gloss(u'a',tuple(['ps']),'gloss',()).matches(Gloss(u'',tuple([]),'gloss',())))
        self.assertEquals(True, Gloss(u'a',tuple(['n','adj']),'gloss',()).matches(Gloss(u'a',tuple(['n']),'',())))
        self.assertEquals(True, Gloss(u'a',tuple(['n','adj']),'',()).matches(Gloss(u'a',tuple(['n']),'',())))
        self.assertEquals(False, emptyGloss.matches(Gloss(u'a',tuple([]),'',())))
        self.assertEquals(False, Gloss(u'a',tuple(['ps']),'',()).matches(Gloss(u'',tuple([]),'gloss',())))
        self.assertEquals(False, Gloss(u'a',tuple(['ps']),'gloss',()).matches(Gloss(u'b',tuple(['ps']),'gloss',())))
        self.assertEquals(False, Gloss(u'a',tuple(['n','adj']),'gloss',()).matches(Gloss(u'b',tuple(['n']),'',())))
        self.assertEquals(False, Gloss(u'a',tuple(['n','adj']),'gloss',()).matches(Gloss(u'b',tuple(['v']),'',())))
        self.assertEquals(False, Gloss(u'sira',tuple(['n']),'gloss',()).matches(Gloss(u'',tuple(['v']),'',())))
        self.assertEquals(False, Gloss(u'w',tuple([]),'',()).matches(Gloss(u'w',tuple(['mrph']),'PL',())))
        # test regex capabilities
        self.assertEquals(True, Gloss(u'a',tuple(['n']),'gloss',()).matches(self.gre))
        self.assertEquals(True, Gloss(u'b',tuple(['n']),'ge',()).matches(self.gre))
        self.assertEquals(False, emptyGloss.matches(self.gre))

    def test_gloss_union(self):
        # test gloss union (typical use: union with pattern data)
        # NB: empty gloss always returns empty union
        self.assertEquals(None, emptyGloss.union(emptyGloss))
        self.assertEquals(u'á:ps:gloss', unicode(Gloss(u'a',tuple([]),'',()).union(Gloss(u'á',tuple(['ps']),'gloss',()))))
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a',tuple(['ps']),'gloss',()).union(emptyGloss)))
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a',tuple(['n','adj']),'gloss',()).union(Gloss(u'a',tuple(['n']),'',()))))
        self.assertEquals(u'a:ps:gloss', unicode(Gloss(u'a',tuple(['ps']),'',()).union(Gloss(u'',tuple([]),'gloss',()))))
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a',tuple(['n','adj']),'',()).union(Gloss(u'',tuple(['n']),'gloss',()))))
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a',tuple([]),'',()).union(Gloss(u'',tuple(['n']),'gloss',()))))
        self.assertEquals(u'None', unicode(emptyGloss.union(Gloss(u'a',tuple([]),'',()))))
        self.assertEquals(u'b:n:gloss', unicode(Gloss(u'a',tuple(['n','adj']),'gloss',()).union(Gloss(u'b',tuple(['n']),'',()))))
        self.assertEquals(u'None', unicode(Gloss(u'a',tuple(['n','adj']),'gloss',()).union(Gloss(u'b',tuple(['v']),'',()))))
        self.assertEquals(u'ab:n:gloss, [a:n:gloss, b:mrph:ge]', unicode(self.gam.union(self.ga)))
        self.assertEquals(u'ab:n:gloss, [a:n:gloss, b:mrph:ge]', unicode(self.gam.union(self.m)))
        # test morphemes union by pattern
        self.assertEquals(u'ab::, [a::1, b::2]', unicode(Gloss('ab',tuple([]),'', (Gloss('a',tuple([]),'',()), Gloss('b',tuple([]),'',()))).union(Gloss('',tuple([]),'', (Gloss('',tuple([]),'2',()), Gloss('',tuple([]),'1',()))), pattern=(1,0))))
        # test regex capabilities
        self.assertEquals(u'a:n:gloss', unicode(Gloss(u'a',tuple(['n']),'gloss',()).union(self.gre)))

    def test_gloss_html(self):
        # text Gloss coercing to html
        self.assertEquals('<span class="w">ab<sub class="ps">n</sub><sub class="gloss">gloss</sub></span>', 
                e.tostring(self.ga.html()))
        self.assertEquals('<span class="w">ab<sub class="ps">n</sub><sub class="gloss">gloss</sub><span class="m">a<sub class="ps">n</sub><sub class="gloss">gloss</sub></span><span class="m">b<sub class="ps">mrph</sub><sub class="gloss">ge</sub></span></span>', 
                e.tostring(self.gam.html()))
            
    def test_pattern(self):
        self.assertEquals(True, self.pat.matches(self.ga))
        self.assertEquals(False, self.pat.matches(self.gam))
        self.assertEquals(unicode(self.gam), unicode(self.pat.apply(self.ga)))


if __name__ == '__main__':
    unittest.main()
