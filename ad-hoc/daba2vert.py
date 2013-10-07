#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import optparse
import argparse
import formats
import cPickle
from orthography import detone

INFLECTION = [
    'PROG',
    'PFV.INTR',
    'PL',
    'PTCP.PRIV',
    'PTCP.POT',
    'RES'
    ]

class VariantsLoader(object):
    def __init__(self, filename):
        cachefile = ''.join([filename, '.variants.cache'])
        if os.path.exists(cachefile) and os.path.getmtime(cachefile) > os.path.getmtime(filename):
            with open(cachefile, 'rb') as cache:
                self.vardict = cPickle.load(cache)
        else:
            self.vardict = formats.DictReader(filename, store=False, variants=True).getVariants()
            with open(cachefile, 'wb') as cache:
                cPickle.dump(self.vardict, cache)

    def get(self):
        return self.vardict

def dedot(s, repl=''):
    return s.replace('.', repl)

def print_token(token, args, vardict):
    gt = formats.GlossToken(token)
    if gt.type == 'Comment':
        return
    print u"{0}\t".format(gt.token).encode('utf-8'),
    if gt.type == 'w':
        if args.tonal:
            get_lemma = lambda x: ''.join(c for c in x if c not in '.')
        elif args.nullify:
            nullify_dict={u'ɔ': 'o', u'ɛ': 'e', u'ɲ': 'ny'}
            def get_lemma(x):
                x = detone(''.join(c for c in x if c not in '.'))
                for source, target in nullify_dict.items():
                    x = x.replace(source, target)
                return x
        else:
            get_lemma = lambda x: detone(''.join(c for c in x if c not in '.'))

        #tonals = []
        lemmas = []
        forms = []
        tags = set([])
        glosses = []
        deep = []
        for g in gt.glosslist:
            tags = tags.union(g.ps)
            glosses.append(dedot(g.gloss, '_'))
            if g.morphemes:
                #HACK: if we have no gloss on the top, make up lemma from morphemes
                # targeted at inflected forms analyzed by the parser
                lemmas.append(get_lemma(''.join([dedot(m.form) for m in g.morphemes if m.gloss not in INFLECTION])))
                if not g.gloss:
                    forms.append('-'.join([dedot(m.form) for m in g.morphemes]))
                    gls = []
                    for m in g.morphemes:
                        if m.gloss.isupper():
                            gls.append(m.gloss)
                        else:
                            gls.append(dedot(m.gloss, '_'))
                    glosses.append('-'.join(gls))
                else:
                    forms.append(dedot(g.form))
                for m in g.morphemes:
                    # add grammatical glosses to tags
                    if m.gloss.isupper():
                        tags.add(m.gloss)
                    if 'mrph' not in m.ps:
                        deep.append(get_lemma(m.form))
                        #deep.append(m.gloss)
            else:
                forms.append(dedot(g.form))
                lemmas.append(get_lemma(g.form))

            if args.variants:
                if g in vardict:
                    for variant in vardict[g]:
                        lemmas.append(get_lemma(variant))
                
        if args.unique:
            print u"\t".join([u'|'.join(filter(None, set(s))) for s in [lemmas, tags, forms, glosses, deep]]).encode('utf-8')
        else:
            print u"\t".join([u'|'.join(filter(None, s)) for s in [lemmas, tags, forms, glosses, deep]]).encode('utf-8')
    else:
        print u"\t".join([gt.token, gt.type, gt.token, gt.token, gt.token]).encode('utf-8')

def main():
    oparser = argparse.ArgumentParser(description='Native Daba format to vertical format converter')
    oparser.add_argument('infile', help='Input file (.html)')
    oparser.add_argument("-t", "--tonal", action="store_true", help="Make tonal lemmas")
    oparser.add_argument("-u", "--unique", action="store_true", help="Print only unique lemmas and glosses")
    oparser.add_argument("-n", "--nullify", action="store_true", help="Transliterate all non-ascii characters")
    oparser.add_argument("-v", "--variants", help="Treat all variants in given dictionary as alternative lemmas")
    args = oparser.parse_args()

    reader = formats.HtmlReader(args.infile)

    if args.variants:
        vardict = VariantsLoader(args.variants).get()
    else:
        vardict = None

    print "<doc ",
    print u'id="{0}"'.format(os.path.basename(args.infile)).encode('utf-8'),
    
    metad = dict(reader.metadata)
    print u'source_type="{0}"'.format(metad.setdefault('source:type', 'UNDEF')).encode('utf-8'),
    print u'source_year="{0}"'.format(metad.setdefault('source:year', 'UNDEF')).encode('utf-8'),
    print u'text_translation="{0}"'.format(metad.setdefault('text:translation', 'UNDEF')).encode('utf-8'),
    print u'text_medium="{0}"'.format(metad.setdefault('text:medium', 'UNDEF')).encode('utf-8'),
    print u'author_name="{0}"'.format(metad.setdefault('author:name', 'UNDEF')).encode('utf-8'),

    try:
        genres = metad['text:genre'].split(';')
        hgenres = [g.split(' : ')[0] for g in genres] + genres
        hgenres.sort()
        metad['text:genre'] = u';'.join(hgenres)
        print u'text_genre="{0}"'.format(metad['text:genre']).encode('utf-8'),
    except (KeyError):
        print 'text_genre="UNDEF"',
    try:
        print u'text_title="{0}"'.format(metad['text:title']).encode('utf-8'),
    except (KeyError):
        print 'text_title="UNDEF"',
    print ">"

    for par in reader.glosses:
        print "<p>"
        for sent,annot in par:
            print "<s>"
            for token in annot:
                print_token(token, args, vardict)
            print "</s>"
        print "</p>"

    print "</doc>"

if __name__ == '__main__':
    main()


