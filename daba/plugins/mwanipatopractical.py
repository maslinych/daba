#!/usr/bin/env python3
# coding: utf-8

from . import OrthographyConverter
import re
import unicodedata


class MwanIPAtoPractical(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'mwanipatopractical'
        self.desc = u'Convertor from Mwan “IPA” orthography into “practical” orthography'

    def convert(self, token):
        """
        Main conversion method
        * макрон просто снять во всех случаях
        * B с хвостом(IPA) > bh (и заглавную)
        * тильду на гласном > n после гласного (или двух, если два)
        * (ny)a > yan (после 1 или 2 гласных)
        * vowel list: 'aouieɛɔ'; tones list '\u0300\u0301\u0302'
        """
        token = unicodedata.normalize('NFKD', token)
        token = token.replace(u'\u0304', '')
        token = token.replace(u'ɓ', u'bh')
        token = token.replace(u'Ɓ', u'Bh')
        token = re.sub(
            u'(([aouieɛɔAOUIEƐƆ]\u0330[\u0300\u0301\u0302]?){1,2})',
            r'\1n', token)
        token = token.replace(u'\u0330', '')
        token = re.sub(
            u'[ɲƝ](([aouieɛɔAOUIEƐƆ][\u0300\u0301\u0302]?)+)',
            r'y\1n', token)
        token = token.replace(u'ɲ', u'y')
        token = token.replace(u'Ɲ', u'Y')
        return token

