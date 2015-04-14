#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import fnmatch
import argparse
from collections import defaultdict
import mparser
import formats
from orthography import detone

dedot = lambda s: u''.join([c for c in s if c not in '.'])

def print_line(form, result):
    result = list(set(result))
    result.sort()
    sys.stdout.write(u'{}\t{}\n'.format(form, u'\t'.join(result)).encode('utf-8'))

def make_taglist(glosses):
    result = []
    for g in glosses:
        lemma = dedot(g.form)
        for tag in g.ps:
            result.append(u' '.join([tag, lemma]))
    return result

def main():
    aparser = argparse.ArgumentParser(description='Lexicon printer for TreeTagger training')
    aparser.add_argument("-r", "--runtimedir", help="Runtime dir with binary saved dictionaries")
    aparser.add_argument("-t", "--tonal", action="store_true", help="Preserve tones on word forms")
    aparser.add_argument("-j", "--join", action="store_true", help="Join all sources")
    aparser.add_argument("-c", "--corpus", default=None, help="Corpus root")
    args = aparser.parse_args()


    if args.join:
        globaldict = defaultdict(list)

    if args.runtimedir:
        seenkeys = set()
        dictionary = mparser.DictLoader(runtimedir=args.runtimedir).dictionary
        for form in dictionary:
            if ' ' not in form:
                if not args.tonal:
                    form = detone(form)
                if form not in seenkeys:
                    glosses = dictionary[form]
                    result = make_taglist(glosses)
                    seenkeys.add(form)
                    if args.join:
                        globaldict[form].extend(result)
                    else:
                        print_line(form, result)

    if args.corpus:
        seentokens = set()
        parsfiles = []
        for root, dirnames, filenames in os.walk(args.corpus):
            for filename in fnmatch.filter(filenames, '*.pars.html'):
                parsfile = os.path.join(root, filename)
                reader = formats.HtmlReader(parsfile)
                for token in reader:
                    if token.type == 'w':
                        form = dedot(token.glosslist[0].form)
                        if not args.tonal:
                            form = detone(form)
                        else:
                            # FIXME: unsupported tonal for corpus
                            pass
                        if form not in seentokens:
                            result = make_taglist(token.glosslist)
                            seentokens.add(form)
                            if args.join:
                                globaldict[form].extend(result)
                            else:
                                print_line(form, result)

    if args.join:
        for form, result in globaldict.iteritems():
            print_line(form, result)


if __name__ == '__main__':
    main()
