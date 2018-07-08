#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
from collections import defaultdict
import daba.mparser
import daba.formats
from daba.orthography import detone
from daba2vert import INFLECTION


dedot = lambda s: u''.join([c for c in s if c not in '.'])


def deduplicate_lemmas(result):
    result = list(set(result))
    result.sort(reverse=True)
    try:
        return list(dict(result).items())
    except ValueError:
        print result
        return result


def print_line(form, result):
    result = deduplicate_lemmas(result)
    sys.stdout.write(u'{}\t{}\n'.format(form, u'\t'.join([' '.join(r) for r in result])).encode('utf-8'))


def make_lemma(gloss):
    if not gloss.gloss and gloss.morphemes:
        return ''.join([dedot(m.form) for m in gloss.morphemes if m.gloss not in INFLECTION])
    else:
        return dedot(gloss.form)


def make_taglist(glosses, formforlemma=False, tonal=False):
    result = []
    for g in glosses:
        if formforlemma:
            lemma = dedot(g.form)
        else:
            lemma = make_lemma(g)
        if not tonal:
            lemma = detone(lemma)
        for tag in g.ps:
            result.append((tag, lemma))
    return result


def main():
    aparser = argparse.ArgumentParser(description='Lexicon printer for TreeTagger training')
    aparser.add_argument("-r", "--runtimedir", help="Runtime dir with binary saved dictionaries")
    aparser.add_argument("-t", "--tonal", action="store_true", help="Preserve tones on word forms")
    aparser.add_argument("-j", "--join", action="store_true", help="Join all sources")
    aparser.add_argument("-p", "--plain", action="store_true", help="Output plain lists of tokens")
    aparser.add_argument("-c", "--corpus", default=None, help="Corpus root")
    aparser.add_argument("-l", "--filelist", action="store", help="List of corpus files to parse")
    aparser.add_argument("-n", "--nopunct", action="store_true", help="Skip punctuation")
    args = aparser.parse_args()

    #locale.setlocale(locale.LC_ALL, 'bm_ML')

    if args.join:
        globaldict = defaultdict(list)

    if args.corpus:
        seentokens = set()
        filelist = []
        with open(args.filelist, 'r') as f:
            for line in f:
                filelist.append(line.decode('utf-8').strip())
        for filename in filelist:
            parsfile = os.path.join(args.corpus, filename)
            reader = daba.formats.HtmlReader(parsfile)
            lastpunct = None
            for token in reader:
                if token.type == 'w':
                    if not args.nopunct and lastpunct:
                        punct = [(lastpunct.type, lastpunct.value)]
                        if args.join:
                            globaldict[lastpunct.value.strip()].extend(punct)
                        else:
                            print_line(lastpunct.value.strip(), punct)
                        lastpunct = None
                    form = dedot(token.glosslist[0].form).lower()
                    if not args.tonal:
                        form = detone(form)
                    else:
                    # FIXME: unsupported tonal for corpus
                        pass
                    if args.plain:
                        result = make_taglist(token.glosslist, tonal=args.tonal)
                        print_line(form, result)
                    else:
                        if form not in seentokens:
                            result = make_taglist(token.glosslist, tonal=args.tonal)
                            seentokens.add(form)
                            if args.join:
                                globaldict[form].extend(result)
                            else:
                                print_line(form, result)
                elif token.type == 'c' and not args.nopunct:
                    lastpunct = token
                elif token.type == '</s>' and not args.nopunct:
                    if lastpunct:
                        punct = [('SENT', lastpunct.value)]
                        if args.join:
                            globaldict[lastpunct.value.strip()].extend(punct)
                        else:
                            print_line(lastpunct.value.strip(), punct)
                        lastpunct = None


    if args.runtimedir:
        seenkeys = set()
        dictionary = daba.mparser.DictLoader(runtimedir=args.runtimedir).dictionary
        for form in dictionary:
            if ' ' not in form:
                if not args.tonal:
                    form = detone(form)
                if args.plain:
                    for gloss in dictionary[form]:
                        print gloss
                        result = make_taglist([gloss], formforlemma=True, tonal=args.tonal)
                        for lemma in result:
                            print_line(form, [lemma])
                else:
                    if args.corpus and form in seentokens:
                        continue
                    if form not in seenkeys:
                        glosses = dictionary[form]
                        result = make_taglist(glosses, formforlemma=True, tonal=args.tonal)
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
