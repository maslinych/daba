#!/usr/bin/env python3
# -*- coding: utf8 -*-

from daba.plugins import OrthographyConverter
import funcparserlib.lexer
import re
import unicodedata


class DukuretoNew(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'dukure'
        self.desc = 'Convertor from Mamadu Dukurɛ (Fakan) orthography'

    def convert(self, token):
        """
        Main conversion method
        """
        conversion_table = {r"^['‘]":[u''], u'-':[u'-', u''], u'ʃ':[u's', u'sh'],
                            u'\u0300':[''], u'à':[u'a'], u'è':[u'e'], u'ì':[u'i'], u'ò':[u'o'], u'ù':[u'u'], u'ὲ':[u'ɛ'],
                            u'\u041B':[u'Ɲ'], u'\u043B':[u'ɲ'], u'ɑ':['a'],  u'ε':['ɛ'],
                            u'ng':[u'ng',u'ŋ'], u'ny':[u'ny',u'ɲ'],
                            u'bl':[u'bil',u'bul'], u'tl':[u'til', u'tul']}
        # apostrophe initiale=article défini: supprimer
        #    critique : le parser l'a déjà détachée comme ponctuation
        #         ça n'est pas toujours vrai : 'kɔnɔ. en fin de phrase ???
        # le tiret intermédiaire est fréquemment utilisé mais met en difficulté gparser : convertir en deux solutions
        # lettre ʃ : convertir: 2 solutions sh ou s
        # ton bas : supprimer
        #    MAIS ils sont le plus souvent traités par des monolithes àè...ὲ ! d'où la 2ème ligne
        #    critique : le parser a déjà divisé les monolithes
        # Accidents fréquents
        # - Л cyrillique : convertir en Ɲ  - minuscule л ajoutée - incertitude ne marche pas sur le dernier mot d'une phrase?
        # - ɑ cyrillique : convertir en a
        # - ε grec : convertir en ɛ
        # ng, ny gardés "au cas où"
        # les majuscules aux verbes, marques prédicatives, copules sont traitées dans un dictionnaire avec \ve
        # contractions: (Bla pour bìla): traitées aussi en dictionnaire ?


        def graphemes_old(word):
            # split word into maximal length graphemes (old orthography)
            specs = [
                    ('NG', (r'ng', re.I | re.U)),
                    ('NY', (r'ny', re.I | re.U)),
                    ('BL', (r'bl', re.I | re.U)),
                    ('TL', (r'tl', re.I | re.U)),
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
        
        x=convertw(token)
        # print("DukuretoNew: ",x)
        return x
