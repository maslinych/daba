#!/usr/bin/python
# -*- coding: utf-8 -*-

from . import OrthographyConverter
import funcparserlib.lexer
import re
import unicodedata
from daba.orthography import detone


class DanOldtoNew(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'danoldtonew'
        self.desc = 'Convertor from old Dan-Gweetaa orthography into new'
        self.conversion_table = {
            u'ɩ': [u'e'],
            u'ɛa': [u'ææ'],
            u'ü': [u'ɯ'],
            u'ʋ̈': [u'ɤ'],
            u'ϋ': [u'ɤ'],
            u'ö': [u'ɤ'],
            u'ë': [u'ʌ'],
            u'ʋ': [u'o'],
            u'υ': [u'o'],
            u'aɔ': [u'œœ'],
            u'ng': [u'ŋ', u'ng'],
            u'r': [u'l'],
            u'’’': [u'"'],
        }
        self.tones = {
            u'"': u'\u030b',
            u'“': u'\u030b',
            u"'": u'\u0301',
            u'‘': u'\u0301',
            u"=": u'\u0300',
            u"-": u'\u030f',
            u"–": u'\u030f',
            u"‑": u'\u030f',
            u"‐": u'\u030f',
        }

    def get_case(self, string):
        string = detone(string)
        if string[0] in [u"-‑‐–=\"'\u2018\u201c"]:
            string = string[1:]
        if string.isupper():
            case = unicode.upper
        elif string.istitle():
            case = unicode.title
        else:
            case = unicode.lower
        return case

    def replace_ng(self, tokens):
        graphemes = []
        for token in tokens:
            if token.type == 'NGG':
                graphemes.append(u'n')
                graphemes.append(u'g')
            elif token.type == 'NGN':
                graphemes.append(u'ŋ')
            else:
                graphemes.append(token.value)
        return graphemes

    def is_multifoot(self, word):
        m = re.match(
            u'.*[auioeɛɔæœɯɤʌʋυ][^auioeɛɔæœɯɤʌʋυ]+[auioeɛɔæœɯɤʌʋυ]',
            word)
        return bool(m)

    def graphemes_old(self, word):
        # split word into maximal length graphemes (old orthography)
        specs = [
                ('EA', (u'ɛa', re.I | re.U)),
                ('AO', (u'aɔ', re.I | re.U)),
                ('NGG', (u'ng(?=[lauioeɛɔæœɯɤʌʋυ])', re.I | re.U)),
                ('NGN', (u'ng(?![blauioeɛɔæœɯɤʌʋυ])', re.I | re.U)),
                ('NGB', (u'ng(?=b)', re.I | re.U)),
                ('V', (u'[OEUƲΥoeuʋυ]\u0308', re.U)),
                ('HT', (u'’’', re.U)),
                ('ANY', (u'.', re.U)),
                ]
        tok = funcparserlib.lexer.make_tokenizer(specs)
        r = [x for x in tok(unicodedata.normalize('NFKD', word))]
        # print 'CW', word, ':', r
        return self.replace_ng(r)

    def multiply_list(self, amblist):
        # given list of lists, returns list of all possible concatenations
        # taking a single element from each list
        def multiply_list_aux(l, amblist):
            if len(amblist) > 0:
                m = []
                for i in range(len(amblist[0])):
                    for k in range(len(l)):
                        m.append(l[k]+[amblist[0][i]])
                return multiply_list_aux(m, amblist[1:])
            else:
                return l
        return multiply_list_aux([[]], amblist)

    def convertg(self, grapheme):
        # convert a single grapheme into a list of corresponding graphemes
        # in new orthography
        if unicodedata.category(grapheme[0]) == 'Lu':
            case = unicode.title
        else:
            case = unicode.lower
        grapheme = unicodedata.normalize('NFKD', grapheme)
        try:
            return [case(g) for g in self.conversion_table[grapheme.lower()]]
        except KeyError:
            return [grapheme]

    def nasalsub(self, match):
        s = match.group(0)
        if s.startswith('m'):
            return u'bh{}n'.format(s[1:])
        elif s.startswith('n'):
            return u'dh{}n'.format(s[1:])
        else:
            return s

    def convert_nasals(self, word):
        # given a single word converts nasals in it
        case = self.get_case(word)
        word = re.sub(u'''
        (
        m([ls]?)
        ([auioeɛɔæœɯɤʌʋυ][\u0300\u0301\u0304\u030b\u030f]?)+
        |
        n(?![^auioeɛɔæœɯɤʌʋυrlsŋ])
        ([rls]?)
        ([auioeɛɔæœɯɤʌʋυ][\u0300\u0301\u0304\u030b\u030f]?)+
        )''',
                      self.nasalsub, word.lower(), flags=re.VERBOSE)
        return case(word)

    def convert_tones(self, word):
        out = []
        if word == u'din-':
            return u'di\u0304n\u0300'
        for tone in self.tones:
            if word.startswith(tone):
                starttone = self.tones[tone]
                break
        else:
            starttone = u'\u0304'
            word = ' ' + word
        word = re.sub(u"(.*?[auioeɛɔæœɯɤʌʋυ])",
                      u"\\1{}".format(starttone),
                      word[1:], count=1, flags=re.I | re.U)
        for tone in self.tones:
            if word.endswith(tone):
                word = word[:-1]
                v = re.match(
                    u'^.*([auioeɛɔæœɯɤʌʋυŋ][\u0300\u0301\u0304\u030b\u030f]?)',
                    word, flags=re.I | re.U)
                if v:
                    if v.group(1).endswith(u'\u0301') and tone in [u'-', u'–', u'‑', u'‐']:
                        out = [u''.join([word[:v.end(1)-1],
                                         u'\u0302',
                                         word[v.end(1):]]),
                               u''.join([word, "'"])]
                    elif word[v.end(1)-1] in u'\u0300\u0304\u030b\u030f':
                        if tone in [u'-', u'–', u'‑', u'‐']:
                            out = [u''.join([word, "'"])]
                        else:
                            out = [u''.join([word[:v.end(1)],
                                            word[v.start(1)],
                                            self.tones[tone],
                                            word[v.end(1):]])]
                    else:
                        out = [u''.join([word[:v.end(1)],
                                        self.tones[tone],
                                        word[v.end(1):]])]
                break
        return out or [word]

    def convert(self, token):
        """
        Main conversion method
        """
        graphemes = [self.convertg(g) for g in self.graphemes_old(token)]
        variants = [''.join(w) for w in self.multiply_list(graphemes)]
        if any(g in [[u'n'], [u'm'], [u'N'], [u'M']] for g in graphemes):
            variants = [self.convert_nasals(v) for v in variants]
        out = []
        for v in variants:
            out.extend(self.convert_tones(v))
        if all(self.is_multifoot(v) for v in variants):
            out.append(u'')
        return out
