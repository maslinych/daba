#!/usr/bin/python
# -*- coding: utf-8 -*-

from . import OrthographyConverter
import funcparserlib.lexer
import re
import unicodedata


class DanOldtoNew(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'danoldtonew'
        self.desc = 'Convertor from old Dan-Gweetaa orthography into new'
        self.conversion_table = {
            u'ɩ': [u'e'],
            u'ɛa': [u'ææ'],
            u'ü': [u'ɯ'],
            u'ʋ̈': [u'ɤ'],
            u'ö': [u'ɤ'],
            u'ë': [u'ʌ'],
            u'ʋ': [u'o'],
            u'aɔ': [u'œœ'],
            u'ng': [u'ŋ', u'ng'],
            u'r': [u'l'],
        }
        self.tones = {
            u'"': u'\u030b',
            u"'": u'\u0301',
            u'‘': u'\u0301',
            u"=": u'\u0300',
            u"-": u'\u030f',
        }

    def get_case(self, string):
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

    def graphemes_old(self, word):
        # split word into maximal length graphemes (old orthography)
        specs = [
                ('EA', (u'ɛa', re.I | re.U)),
                ('AO', (u'aɔ', re.I | re.U)),
                ('NGG', (u'ng(?=[lauioeɛɔæœɯɤʌ])', re.I | re.U)),
                ('NGN', (u'ng(?![blauioeɛɔæœɯɤʌ])', re.I | re.U)),
                ('NGB', (u'ng(?=b)', re.I | re.U)),
                ('V', (u'[oeuʋ]\u0308', re.U)),
                ('ANY', (u'.', re.U)),
                ]
        tok = funcparserlib.lexer.make_tokenizer(specs)
        r = [x for x in tok(unicodedata.normalize('NFKD', word))]
        # print 'CW', string, ':', r
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
        try:
            case = self.get_case(grapheme)
            return [case(g) for g in self.conversion_table[grapheme.lower()]]
        except KeyError:
            return [grapheme]

    def convert_nasals(self, word):
        # given a single word converts nasals in it
        case = self.get_case(word)
        word = re.sub(u'(m)(l?[auioeɛɔæœɯɤʌ]+)', u'bh\\2n', word.lower())
        word = re.sub(u'(n)(l?[auioeɛɔæœɯɤʌ]+)', u'dh\\2n', word.lower())
        return case(word)

    def convert_tones(self, word):
        if word == u'din-':
            return u'di\u0304n\u0300'
        for tone in self.tones:
            if word.startswith(tone):
                starttone = self.tones[tone]
                break
        else:
            starttone = u'\u0304'
            word = ' ' + word
        word = re.sub(u"(.*?[auioeɛɔæœɯɤʌ])",
                      u"\\1{}".format(starttone),
                      word[1:], count=1)
        for tone in self.tones:
            if word.endswith(tone):
                word = word[:-1]
                v = re.match(
                    u'^.*([auioeɛɔæœɯɤʌŋ][\u0300\u0301\u0304\u030b\u030f]?)',
                    word)
                if v:
                    if v.group(1).endswith(u'\u0301') and tone == '-':
                        word = ''.join([word[:v.end(1)-1],
                                        u'\u0302',
                                        word[v.end(1):]])
                    elif word[v.end(1)-1] in '\u0300\u0304\u030b\u030f':
                        word = ''.join([word[:v.end(1)],
                                        word[v.start(1)],
                                        self.tones[tone],
                                        word[v.end(1):]])
                    else:
                        word = ''.join([word[:v.end(1)],
                                        self.tones[tone],
                                        word[v.end(1):]])
                break
        return word

    def convert(self, token):
        """
        Main conversion method
        """
        graphemes = [self.convertg(g) for g in self.graphemes_old(token)]
        variants = [''.join(w) for w in self.multiply_list(graphemes)]
        if any(g in [[u'n'], [u'm']] for g in graphemes):
            variants = [self.convert_nasals(v) for v in variants]
        variants = [self.convert_tones(v) for v in variants]
        return variants
