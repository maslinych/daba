#!/usr/bin/env python3
# -*- coding: utf8 -*-

from daba.plugins import OrthographyConverter
import funcparserlib.lexer
import re
import unicodedata


class ThoyertoNew(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'thoyer'
        self.desc = 'Convertor from Annik Thoyer transcriptions 1978'

    def convert(self, token):
        """
        Main conversion method
        """
        conversion_table = {u'èè':[u'ɛɛ'], u'òò':[u'ɔɔ'], u'èe':[u'ɛɛ'], u'òo':[u'ɔɔ'], u'è':[u'ɛ'], u'ò':[u'ɔ'], 
                            u'ng':[u'ng',u'ŋ'], u'ny':[u'ny',u'ɲ'], 
                            u'sy':[u'sh', u's'], u'y':[u'y', u'j'], u'gh':[u'g'], u'gb':[u'g'], u'gw':[u'g',u'j',u'gw']}

        def graphemes_old(word):
            # split word into maximal length graphemes (old orthography)
            specs = [
                    ('NG', (r'ng', re.I | re.U)),
                    ('NY', (r'ny', re.I | re.U)),
                    ('EE', (r'è[eè]', re.I | re.U)),
                    ('OO', (r'ò[oò]', re.I | re.U)),
                    ('GH', (r'gh', re.I | re.U)),
                    ('GB', (r'gb', re.I | re.U)),
                    ('GW', (r'gw', re.I | re.U)),
                    ('SY', (r'sy', re.I | re.U)),
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
