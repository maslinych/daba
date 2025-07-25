#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import html
import argparse
import daba.formats
import pickle
import unicodedata
from daba.orthography import detone

INFLECTION = [
    'PROG',
    'PFV.INTR',
    'PL',
    'PTCP.PRIV',
    'PTCP.POT',
    'PTCP.RES',
    'PTCP.PROG',
    'RES',
    'ART',
    'INF',
    'PTCP.NEG',
    'IMMED',
    'AOR.INTR'
    ]


class VariantsLoader(object):
    def __init__(self, filename):
        cachefile = ''.join([filename, '.variants.cache'])
        if os.path.exists(cachefile) and os.path.getmtime(cachefile) > os.path.getmtime(filename):
            with open(cachefile, 'rb') as cache:
                self.vardict, self.polisemy = pickle.load(cache)
        else:
            reader = daba.formats.DictReader(filename, store=False, variants=True, polisemy=True)
            self.vardict = reader.getVariants()
            self.polisemy = reader.getPolisemy()
            with open(cachefile, 'wb') as cache:
                pickle.dump((self.vardict, self.polisemy), cache)

    def get(self):
        return self.vardict, self.polisemy


def dedot(s, repl=''):
    if '|' in s:
        s = s.split("|")[0]
    if ' ' in s:
        s = s.replace(" ", "_")
    return s.replace('.', repl)


def print_fields(fields, unique=True):
    if unique:
        print(u"\t".join([u'|'.join(filter(None, set(s))) for s in fields]))
    else:
        print(u"\t".join([u'|'.join(filter(None, s)) for s in fields]))


def make_lemmafunc(args):
    if args.tonal:
        get_lemma = lambda x: dedot(x)
    elif args.nullify:
        nullify_dict={u'ɔ': 'o', u'ɛ': 'e', u'ɲ': 'ny'}
        def get_lemma(x):
            x = detone(''.join(c for c in x if c not in '.'))
            for source, target in nullify_dict.items():
                x = x.replace(source, target)
            return x
    else:
        get_lemma = lambda x: detone(dedot(x))
    return get_lemma


def make_tagstring(gloss):
    if gloss.morphemes:
        mtags = u' [{}]'.format(u' '.join(map(make_tagstring, [m for m in gloss.morphemes])))
    else:
        mtags = u''
    return u'/'.join(gloss.ps or '_') + mtags


def print_token(gt, args, vardict, polidict, get_lemma, sent=False):
    if gt.type in ['Comment', '<s>', '<p>']:
        return
    if not gt.type == "w":
        if gt.value:
           print(gt.token, end="\t")
    if gt.type == 'w':
        normalized = gt.glosslist[0].form
        if ' ' in normalized:
            words = normalized.split(' ')
            for word in words:
                gt.glosslist[0] = gt.glosslist[0]._replace(form=word)
                print_token(gt, args, vardict, polidict, get_lemma, sent=sent)
            return
        if args.convert and not args.keepsource:
            token = get_lemma(normalized)
            if args.tonal and args.conll:
                token = detone(token)
        else:
            token = gt.token
        print(token, end="\t")

        tonals = []
        fields = []
        lemmas = []
        tags = set()
        glosses = []
        igtforms = []
        igtglosses = []
        deep = []
        polisemy = []
        for g in gt.glosslist:
            tags = tags.union(g.ps)
            if re.match(r'^[A-Z0-9.]+$', g.gloss):
                gls = g.gloss
            else:
                gls = dedot(g.gloss, '_')
            if not gls and g.morphemes:
                gls = '-'.join([m.gloss for m in g.morphemes])
            if not args.nogloss:
                gls = unicodedata.normalize('NFKC', gls)
                glosses.append(gls)
            if not args.tonal:
                if g.morphemes:
                    tonals.append(''.join([dedot(m.form) for m in g.morphemes]))
                else:
                    tonals.append(dedot(g.form))
            if g.morphemes:
                #HACK: if we have no gloss on the top, make up lemma from morphemes
                # targeted at inflected forms analyzed by the parser
                if [m for m in g.morphemes if 'mrph' not in m.ps]:
                    lemmas.append(get_lemma(''.join([dedot(m.form) for m in g.morphemes if m.gloss not in args.flective.split(',')])))
                else:
                    lemmas.append(get_lemma(g.form))

                if args.igt:
                    if not g.gloss:
                        igtforms.append('-'.join([dedot(m.form) for m in g.morphemes]))
                        gls = []
                        for m in g.morphemes:
                            if m.gloss.isupper():
                                gls.append(m.gloss)
                            else:
                                gls.append(dedot(m.gloss, '_'))
                        igtglosses.append('-'.join(gls))
                    else:
                        igtforms.append(dedot(g.form))
                for m in g.morphemes:
                    if not args.conll:
                        # add grammatical glosses to tags
                        if m.gloss.isupper():
                            tags.add(m.gloss)
                    else:
                            glosses.append(m.gloss)
                    if 'mrph' not in m.ps:
                        deep.append(get_lemma(m.form))
                        #deep.append(m.gloss)
            else:
                if args.igt:
                    igtforms.append(dedot(g.form))
                lemmas.append(get_lemma(g.form))

            if args.variants:
                if g in vardict:
                    if args.canonical:
                        try:
                            lemmas = [get_lemma(vardict[g][0])]
                        except IndexError:
                            pass
                    else:
                        for variant in vardict[g]:
                            lemmas.append(get_lemma(variant))
                
            #HACK truncate extra long glosses lists
            if len(glosses)>10:
                glosses = glosses[:10]
                glosses.append('...')

            fields = [lemmas, tags, glosses, deep]

            if args.convert:
                if args.keepsource:
                    fields.append([normalized])
                else:
                    fields.append([gt.token])

            if not args.tonal:
                fields.append(tonals)

            if args.polisemy:
                for ge, gvs in polidict[dedot(g.form)].items():
                    if dedot(ge, '_') in glosses:
                        polisemy.extend(gvs)
                fields.append(polisemy)
            
            if args.igt:
                fields.append(igtforms)
                fields.append(igtglosses)

            if args.debugfields:
                fields.append([make_tagstring(g) for g in gt.glosslist])
                
        print_fields(fields, unique=args.unique)

    else:
        nfields = 5
        if args.polisemy:
            nfields += 1
        if args.igt:
            nfields += 2
        if args.convert:
            nfields += 1
        if not args.tonal:
            nfields += 1
        if args.debugfields:
            nfields += 1

        if sent and gt.type == 'c':
            ctag = args.senttag
        else:
            ctag = gt.type
        print(u"\t".join([gt.token, ctag] + [gt.token]*(nfields-2)))


def print_metafield(name, store):
    value = html.escape(store.setdefault(name, 'UNDEF'))
    print(u'{0}="{1}"'.format(name.replace(':', '_'), value), end=" ")


def reversedEnumerate(l):
    return zip(range(len(l)-1, -1, -1), l)


def main():
    oparser = argparse.ArgumentParser(description='Native Daba format to vertical format converter')
    oparser.add_argument('infile', help='Input file (.html)')
    oparser.add_argument("-t", "--tonal", action="store_true", help="Make tonal lemmas")
    oparser.add_argument("-u", "--unique", action="store_true", help="Print only unique lemmas and glosses")
    oparser.add_argument("-n", "--nullify", action="store_true", help="Transliterate all non-ascii characters")
    oparser.add_argument("-v", "--variants", help="Treat all variants in given dictionary as alternative lemmas")
    oparser.add_argument('-N', '--canonical', action='store_true', help='Return canonical lemma (to be used with --variants)')
    oparser.add_argument("-p", "--polisemy", action="store_true", help="Show polisemy in a separate field (suggests -v)")
    oparser.add_argument("-c", "--convert", action="store_true", help="Normalize wordform field, move source to the end")
    oparser.add_argument("-k", "--keepsource", action="store_true", help="Keep source token at the head, to use with --convert")
    oparser.add_argument("-i", "--igt", action="store_true", help="Add morpheme-segmented form/gloss pair suited to copy as IGT examples")
    oparser.add_argument("-d", "--debugfields", action="store_true", help="Add debug fields for Jean-Jacques")
    oparser.add_argument("-f", "--flective", action="store", help="A list of flective morphemes (glosses)", default=','.join(INFLECTION))
    oparser.add_argument("-C", "--conll", action="store_true", help="Output CONLL-compatible format")
    oparser.add_argument("-s", "--senttag", action="store", default="c", help="Tag to use for SentPunct tokens")
    oparser.add_argument("-g", "--nogloss", action="store_true", help="Omit glosses in other language (keep only grammatical)")
    args = oparser.parse_args()

    reader = daba.formats.HtmlReader(args.infile)

    if args.variants:
        vardict, polidict = VariantsLoader(args.variants).get()
    else:
        vardict = None
        polidict = None

    print("<doc", end=" ")
    print(u'id="{0}"'.format(os.path.basename(args.infile)), end=" ")
    
    metad = dict(reader.metadata)
    for f in ['source:type', 'source:year', 'text:translation', 'text:medium', 'author:name']:
        print_metafield(f, metad)
    try:
        genres = metad['text:genre'].split(';')
        hgenres = [g.split(' : ')[0] for g in genres] + genres
        hgenres.sort()
        metad['text:genre'] = u';'.join(hgenres)
        print(u'text_genre="{0}"'.format(metad['text:genre']), end=" ")
    except (KeyError):
        print('text_genre="UNDEF"', end=" ")
    try:
        print_metafield('text:title', metad)
    except (KeyError):
        print('text_title="UNDEF"', end="")
    print(">")

    for par in reader.glosses:
        print("<p>")
        for sent, annot in par:
            print("<s>")
            for i, token in reversedEnumerate(annot):
                if i > 0:
                    print_token(token, args, vardict, polidict, make_lemmafunc(args))
                else:
                    print_token(token, args, vardict, polidict, make_lemmafunc(args), sent=True)
            print("</s>")
        print("</p>")

    print("</doc>")

if __name__ == '__main__':
    main()


