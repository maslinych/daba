#!/usr/bin/env python3
# coding: utf-8
import re

class TokenizerData(object):
    def __init__(self):        
        self.bamana = [
                ('Comment', (r'<c>.*?</c>', re.DOTALL)),
                ('Comment', (r'<sp>.*?</sp>',)),
                ('SentPunct', (r'<st>',)),
                ('SentPunct', (r'([.!?\u061f\u07f9]+(?=[\s\n\u200f])|:(?=\s*\n))', re.UNICODE)),
                ('SentPunct', (u'(?<=[.!?])\s*[»"]', re.UNICODE)),
                # ('SentPunct', (u':(?=\s*[«"])', re.UNICODE)),
                ('Punct', (r'([:;,\u061b\u060c\u07f8\u200f(){}"]+)', re.UNICODE)),
                ('Tag', (r'<.*?>',)),
                ('Par', (r'(\r?\n){2,}',)),
                ('NL', (r'[\r\n]',)),
                ('Space', (r'\s+', re.UNICODE)),
                ('Cardinal', (r'(\d([-.,:]\d)?)+', re.UNICODE)),
                ('Word', (r'[nN]\u00b0', re.UNICODE)),
                ('Word', (r'\d+nan', re.UNICODE)),
                # FIXME: hardcoded acute and grave accents plus round apostrophe (shoud not split words)
                ('Word', (r'(\w\.){2,}', re.UNICODE)),
                ('Word', (r"[\w\u0300\u0301\u0302\u030c\u0308\u07eb\u07ec\u07ed\u07ee\u07ef\u07f0\u07f1\u07f2\u07f3\u07f6\u07fa-]+['\u2019\u07f4\u07f5]", re.UNICODE)),
                ('Word', (r"(\w[\u0300\u0301\u0302\u030c\u0308\u07eb\u07ec\u07ed\u07ee\u07ef\u07f0\u07f1\u07f2\u07f3\u07f6\u07fa-]{0,2})+", re.UNICODE)),
                ('BOM', (u'\ufeff', )),
                ('Nonword', (r'\W', re.UNICODE)),
                ]

        self.nko = [
                ('Comment', (r'<c>.*?</c>', re.DOTALL)),
                ('Comment', (r'<sp>.*?</sp>',)),
                ('SentPunct', (r'<st>',)),
                ('SentPunct', (r'([.!?\u061f\u07f9]+(?=[\s\n\u200f])|:(?=\s*\n))', re.UNICODE)),
                ('SentPunct', (u'(?<=[.!?])\s*[»"]', re.UNICODE)),
                # ('SentPunct', (u':(?=\s*[«"])', re.UNICODE)),
                ('Punct', (r'([:;,\u061b\u060c\u07f8\u200f(){}"_]+)', re.UNICODE)),
                ('Tag', (r'<.*?>',)),
                ('Par', (r'(\r?\n){2,}',)),
                ('NL', (r'[\r\n]',)),
                ('Space', (r'\s+', re.UNICODE)),
                ('Cardinal', (r'(\d([-.,:]\d)?)+', re.UNICODE)),
                ('Word', (r'[nN]\u00b0', re.UNICODE)),
                ('Word', (r'\d+nan', re.UNICODE)),
                # FIXME: hardcoded acute and grave accents plus round apostrophe (shoud not split words)
                ('Word', (r'(\w\.){2,}', re.UNICODE)),
                ('Word', (r"[\w\u0300\u0301\u0302\u030c\u0308\u07eb\u07ec\u07ed\u07ee\u07ef\u07f0\u07f1\u07f2\u07f3\u07f6\u07fa-]+['\u2019\u07f4\u07f5]", re.UNICODE)),
                ('Word', (r"(\w[\u0300\u0301\u0302\u030c\u0308\u07eb\u07ec\u07ed\u07ee\u07ef\u07f0\u07f1\u07f2\u07f3\u07f6\u07fa-]{0,2})+", re.UNICODE)),
                ('BOM', (u'\ufeff', )),
                ('Nonword', (r'\W', re.UNICODE)),
                ]

        self.dan = [
                ('Comment', (u'<c>.*?</c>', re.DOTALL)),
                ('Comment', (u'<sp>.*?</sp>',)),
                ('SentPunct', (u'<st>',)),
                ('SentPunct', (u'([.!?]+(?=[\s\n\u200f])|:(?=\s*\n))', re.UNICODE)),
                ('SentPunct', (u'(?<=[.!?])\s*[»\u203a]+', re.UNICODE)),
                ('Punct', (u'([:;,(){}‹›]+|<\s*<|>\s*>)', re.UNICODE)),
                ('Tag', (u'<.*?>',)),
                ('Par', (u'(\r?\n){2,}',)),
                ('NL', (u'[\r\n]',)),
                ('Space', (u'\s+', re.UNICODE)),
                ('Cardinal', (u'(\d([-.,:]\d)?)+', re.UNICODE)),
                ('Word', (u'(\w\.){2,}', re.UNICODE)),
                ('Word', (u"([=\"'\u2018\u201c–‑‐-]|[’]{1,2}|‘’)?[\w\u0300\u0301\u0302\u0304\u0308\u030b\u030f]+([=\"'\u201c\u201d\u2018\u2010\u2011-]|[\u2019]{1,2})?", re.UNICODE)),
                ('Nonword', (u'\W', re.UNICODE)),
        ]
        
        self.kpelle = [
                ('Comment', (u'<c>.*?</c>', re.DOTALL)),
                ('Comment', (u'<sp>.*?</sp>',)),
                ('SentPunct', (u'<st>',)),
                ('SentPunct', (u'((?<![0-9])[.!?]+(?=[\s\n\u200f])|:(?=\s*\n))', re.UNICODE)),
                ('SentPunct', (u'(?<=[.!?])\s*([»\u203a”]+|’’)', re.UNICODE)),
                ('Punct', (u'([:;,(){}‹›]+|<\s*<|>\s*>|’’|‘‘)', re.UNICODE)),
                ('Tag', (u'<.*?>',)),
                ('Par', (u'(\r?\n){2,}',)),
                ('NL', (u'[\r\n]',)),
                ('Space', (u'\s+', re.UNICODE)),
                ('Cardinal', (u'(\d([-.,:]\d)?)+[.]?', re.UNICODE)),
                ('Word', (u'(\w\.){2,}', re.UNICODE)),
                ('Word', (u"['’‘]?[\w\u0300\u0301\u0302\u0308=-]+", re.UNICODE)),
                ('Nonword', (u'\W', re.UNICODE)),
        ]


        self._methods = {
            "bamana": self.bamana,
            "nko": self.nko,
            "dan": self.dan,
            "kpelle": self.kpelle,
            "default": self.bamana
        }
        self.methods = list(self._methods.keys())

    def get(self, method):
        return self._methods[method]

