#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import fnmatch
import argparse
import locale
from collections import defaultdict
import mparser
import formats
from orthography import detone
from daba2vert import INFLECTION

dedot = lambda s: u''.join([c for c in s if c not in '.'])

def print_line(form, result):
    result = list(set(result))
    result.sort()
    sys.stdout.write(u'{}\t{}\n'.format(form, u'\t'.join(result)).encode('utf-8'))

def make_lemma(gloss):
    if gloss.morphemes:
        return ''.join([dedot(m.form) for m in gloss.morphemes if m.gloss not in INFLECTION])
    else:
        return dedot(gloss.form)

def make_taglist(glosses, formforlemma=False):
    result = []
    for g in glosses:
        if formforlemma:
            lemma = dedot(g.form)
        else:
            lemma = make_lemma(g)
        for tag in g.ps:
            result.append(u' '.join([tag, lemma]))
    return result


def main():
    aparser = argparse.ArgumentParser(description='Lexicon printer for TreeTagger training')
    aparser.add_argument("-r", "--runtimedir", help="Runtime dir with binary saved dictionaries")
    aparser.add_argument("-t", "--tonal", action="store_true", help="Preserve tones on word forms")
    aparser.add_argument("-j", "--join", action="store_true", help="Join all sources")
    aparser.add_argument("-p", "--plain", action="store_true", help="Output plain lists of tokens")
    aparser.add_argument("-c", "--corpus", default=None, help="Corpus root")
    aparser.add_argument("-g", "--glob", default="*.pars.html", help="Filename pattern for search in the corpus dir")
    args = aparser.parse_args()

    #locale.setlocale(locale.LC_ALL, 'bm_ML')

    if args.join:
        globaldict = defaultdict(list)

    if args.corpus:
        seentokens = set()
        parsfiles = []
        for root, dirnames, filenames in os.walk(args.corpus):
            for filename in fnmatch.filter(filenames, args.glob):
                parsfile = os.path.join(root, filename)
                reader = formats.HtmlReader(parsfile)
                lastpunct = None
                for token in reader:
                    if token.type == 'w':
                        if lastpunct:
                            print_line(lastpunct.value, [' '.join([lastpunct.type, lastpunct.value])])
                            lastpunct = None
                        form = dedot(token.glosslist[0].form).lower()
                        if not args.tonal:
                            form = detone(form)
                        else:
                            # FIXME: unsupported tonal for corpus
                            pass
                        if args.plain:
                            result = make_taglist(token.glosslist)
                            print_line(form, result)
                        else:
                            if form not in seentokens:
                                result = make_taglist(token.glosslist)
                                seentokens.add(form)
                                if args.join:
                                    globaldict[form].extend(result)
                                else:
                                    print_line(form, result)
                    elif token.type == 'c':
                        lastpunct = token
                    elif token.type == 's':
                        if lastpunct:
                            print_line(lastpunct.value, [' '.join(['SENT', lastpunct.value])])
                            lastpunct = None


    if args.runtimedir:
        seenkeys = set()
        dictionary = mparser.DictLoader(runtimedir=args.runtimedir).dictionary
        for form in dictionary:
            if ' ' not in form:
                if not args.tonal:
                    form = detone(form)
                if args.plain:
                    for gloss in dictionary[form]:
                        print gloss
                        result = make_taglist([gloss], formforlemma=True)
                        for lemma in result:
                            print_line(form, [lemma])
                else:
                    if args.corpus and form in seentokens:
                        continue
                    if form not in seenkeys:
                        glosses = dictionary[form]
                        result = make_taglist(glosses, formforlemma=True)
                        seenkeys.add(form)
                        if args.join:
                            globaldict[form].extend(result)
                        else:
                            print_line(form, result)

    if args.join:
        for form, result in globaldict.iteritems():
            print_line(form, result)


if __name__ == '__main__':
    main()
