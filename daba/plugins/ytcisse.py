#!/usr/bin/env python3
# -*- coding: utf8 -*-

from daba.plugins import OrthographyConverter
import funcparserlib.lexer
import re
import unicodedata


class YTCissetoNew(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'ytcisse'
        self.desc = 'Convertor from Youssouf Tata Cissé transcriptions of Wa Kamissoko 1976'

    def convert(self, token):
        """
        Main conversion method
        """
        conversion_table = {u'èè':[u'ɛɛ'], u'òò':[u'ɔɔ'], u'èe':[u'ɛɛ'], u'òo':[u'ɔɔ'], u'è':[u'ɛ'], u'ò':[u'ɔ'], 
                            u'ng':[u'ng',u'ŋ'], u'nw':[u'ng',u'nw'], u'ny':[u'ny',u'ɲ'], u'dy':[u'j',u'dy'], u'ty':[u'c',u'ty'], u't':[u't',u'c'], u'k':[u'k',u'g'],
                            u'sh':[u's',u'sh'], u'sy':[u'sh', u's'], u'y':[u'y', u'j'], u'gh':[u'g'], u'gb':[u'g'], u'gw':[u'g',u'j',u'gw'],
                            u'aa':[u'aa',u'a'], u'ee':[u'ee',u'e'], u'ii':[u'ii',u'i'], u'oo':[u'oo',u'o'], u'uu':[u'uu',u'u'], u'ɛɛ':[u'ɛɛ',u'ɛ'], u'ɔɔ':[u'ɔɔ',u'ɔ']}

        def graphemes_old(word):
            # split word into maximal length graphemes (old orthography)
            specs = [
                    ('NG', (r'ng', re.I | re.U)),
                    ('NY', (r'ny', re.I | re.U)),
                    ('NW', (r'nw', re.I | re.U)),
                    ('DY', (r'dy', re.I | re.U)),
                    ('TY', (r'ty', re.I | re.U)),
                    ('EE', (r'è[eè]', re.I | re.U)),
                    ('OO', (r'ò[oò]', re.I | re.U)),
                    ('GH', (r'gh', re.I | re.U)),
                    ('GB', (r'gb', re.I | re.U)),
                    ('GW', (r'gw', re.I | re.U)),
                    ('SH', (r'sh', re.I | re.U)),
                    ('SY', (r'sy', re.I | re.U)),
                    ('A2', (r'aa', re.I | re.U)),
                    ('E2', (r'ee', re.I | re.U)),
                    ('I2', (r'ii', re.I | re.U)),
                    ('O2', (r'oo', re.I | re.U)),
                    ('U2', (r'uu', re.I | re.U)),
                    ('Ɛ2', (r'ɛɛ', re.I | re.U)),
                    ('Ɔ2', (r'ɔɔ', re.I | re.U)),
                    ('ANY', (r'.', re.U)),
                    ]

            tok = funcparserlib.lexer.make_tokenizer(specs)
            r = [x.value for x in tok(unicodedata.normalize('NFKC', word))]

            return r

        def multiply_list(amblist):
            # given list of lists, returns list of all possible concatenations
            # taking a single element from each list
            def multiply_list_aux(l, amblist):
                if len(amblist)>0:
                    m = [ l[k]+[amblist[0][i]] for k in range(len(l)) for i in range(len(amblist[0]))]
                    return multiply_list_aux(m, amblist[1:])
                else:
                    return l
            return multiply_list_aux([[]], amblist)

        def convertg(grapheme):
            # convert a single grapheme into a list of corresponding graphemes in new orthography
            try:
                # !!HACK: converts graphemes to lowercase!!
                return conversion_table[grapheme.lower()]
            except KeyError:
                return [grapheme]

        def convertw(word):
            # given single word in old orthography returns 
            # list of all possible translations to new orthography
            graphemes = [convertg(g) for g in graphemes_old(word)]
            return [''.join(w) for w in multiply_list(graphemes)]
        
        return convertw(token)
