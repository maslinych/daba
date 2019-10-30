#!/usr/bin/env python3
# -*- coding: utf8 -*-

from . import OrthographyConverter
import funcparserlib.lexer
import re
import unicodedata


class BambaraOldtoNew(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'bamlatinold'
        self.desc = 'Convertor from old latin Bambara orthography (ambiguous)'

    def convert(self, token):
        """
        Main conversion method
        """
        conversion_table = {u'è':[u'ɛ'], u'ò':[u'ɔ'], u'èe':[u'ɛɛ'], u'òo':[u'ɔɔ'], u'ng':[u'ng',u'ŋ'], u'ny':[u'ny',u'ɲ']}

        def graphemes_old(word):
            # split word into maximal length graphemes (old orthography)
            specs = [
                    ('NG', (r'ng', re.I | re.U)),
                    ('NY', (r'ny', re.I | re.U)),
                    ('EE', (ur'è[eè]', re.I | re.U)),
                    ('OO', (ur'ò[oò]', re.I | re.U)),
                    ('ANY', (r'.', re.U)),
                    ]
            tok = funcparserlib.lexer.make_tokenizer(specs)
            r = [x.value for x in tok(unicodedata.normalize('NFKC', word))]
            #print 'CW', string, ':', r
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
