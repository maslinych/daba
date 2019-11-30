#!/usr/bin/env python3
# -*- coding: utf8 -*-

from . import OrthographyConverter

class ApostropheNormalizer(OrthographyConverter):
    def __init__(self):
        self.title = 'apostrophe'
        self.desc = 'Convert unicode apostrophe (2019) to ASCII apostrophe (45)'

    def convert(self, word):
        return [str(word).translate({ord(u'\u2019'):ord(u"'")})]
