#!/usr/bin/env python3
# coding: utf-8

import sys
import re
import codecs
import argparse
from daba.formats import DictReader
from daba.ntgloss import Gloss


def print_field(tag, value):
    if not value:
        print(u"\\{}".format(tag).encode("utf-8"))
    elif not tag:
        print(value.encode("utf-8"))
    else:
        print(u"\\{} {}".format(tag, value).encode("utf-8"))


def strip_lemma(lemma):
    try:
        u = str(lemma)
    except TypeError:
        print("ERR: {}".format(repr(lemma)).encode('utf8'))
    if u.startswith('-'):
        return(u[1:])
    else:
        return u


def print_lemmas_mm(lemmas):
    lemmas = list(set(lemmas))
    if len(lemmas) == 1:
        print_field('mm', strip_lemma(lemmas[0]))
    else:
        for lemma in lemmas:
            print_field('mx', strip_lemma(lemma))


def get_mm(part, dic):
    try:
        lemmas = dic[part]
        print_lemmas_mm(lemmas)
    except KeyError:
        if part.startswith('-'):
            try:
                lemmas = dic[part[1:]]
                print_lemmas_mm(lemmas)
            except KeyError:
                print_field('mx', part)


def make_gloss(record, glossfields):
    le = None
    ps = None
    ge = None
    glossdict = {}
    for tag, value in record:
        if tag in ['le', 'lx']:
            le = value
        elif tag in ['ps'] and not ps:
            if value:
                ps = tuple(value.split('/'))
            else:
                ps = ()
        elif tag in glossfields:
            glossdict[tag] = value
    for f in glossfields:
        try:
            ge = glossdict[f]
            break
        except KeyError:
            pass
        ge = ''
    if le:
        return Gloss(le, ps, ge, ())
    else:
        return Gloss('', '', '', ())


def make_mm(record, gloss, dic):
    for tag, value in record:
        print_field(tag, value)
        # композитные формы
        if tag == 'le' and '-' in value:
            parts = value.split('-')
            if not parts[0] or parts[0].isspace():
                # не обрабатываем морфемы вида \le -smth
                continue
            for part in parts:
                get_mm(part, dic)
        elif tag == 'u':
            parts = filter(None, value.split(' '))
            for part in parts:
                if '{' in part:
                    m = re.match('-?([^{]+){([^}]+)}', part)
                    if m:
                        print_field('mm', u"{}:mrph:{}".format(*m.groups()))
                    else:
                        print_field('mx', part)
                elif part == gloss.form:
                    print_field('mm', strip_lemma(gloss))
                else:
                    get_mm(part, dic)
    

def main():
    aparser = argparse.ArgumentParser(
        description="Add \mm fields under \u for each morpheme")
    aparser.add_argument('dictfile', help='Dictionary to process')
    aparser.add_argument('-g', '--glossfields', action='append')
    args = aparser.parse_args()
    
    dic = DictReader(args.dictfile,
                     variants=True,
                     keepmrph=True,
                     normalize=False,
                     glossfields=args.glossfields).get()

    with codecs.open(args.dictfile, 'r', encoding="utf-8") as dictfile:
        record = []
        for line in dictfile:
            if not line or line.isspace():
                gloss = make_gloss(record, args.glossfields)
                make_mm(record, gloss, dic)
                record = []
                print("")
            elif line.startswith('\\'):
                tag, space, value = line[1:].strip().partition(' ')
                record.append((tag, value))
            else:
                record.append((None, line.strip()))
        else:
            gloss = make_gloss(record, args.glossfields)
            make_mm(record, gloss, dic)


if __name__ == '__main__':
    main()
