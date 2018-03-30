#!/usr/bin/env python
# coding: utf-8
import re

class TokenizerData(object):
    def __init__(self):        
        self.bamana = [
                ('Comment', (r'<c>.*?</c>', re.DOTALL)),
                ('Comment', (r'<sp>.*?</sp>',)),
                ('SentPunct', (r'<st>',)),
                ('SentPunct', (ur'([.!?\u061f\u07f9]+(?=[\s\n\u200f])|:(?=\s*\n))', re.UNICODE)),
                ('SentPunct', (u'(?<=[.!?])\s*[»"]', re.UNICODE)),
                # ('SentPunct', (u':(?=\s*[«"])', re.UNICODE)),
                ('Punct', (ur'([:;,\u061b\u060c\u07f8\u200f(){}"]+)', re.UNICODE)),
                ('Tag', (r'<.*?>',)),
                ('Par', (r'(\r?\n){2,}',)),
                ('NL', (r'[\r\n]',)),
                ('Space', (r'\s+', re.UNICODE)),
                ('Cardinal', (r'(\d([-.,:]\d)?)+', re.UNICODE)),
                ('Word', (ur'[nN]\u00b0', re.UNICODE)),
                ('Word', (r'\d+nan', re.UNICODE)),
                # FIXME: hardcoded acute and grave accents plus round apostrophe (shoud not split words)
                ('Word', (ur'(\w\.){2,}', re.UNICODE)),
                ('Word', (ur"[\w\u0300\u0301\u0302\u030c\u0308\u07eb\u07ec\u07ed\u07ee\u07ef\u07f0\u07f1\u07f2\u07f3\u07f6\u07fa-]+['\u2019\u07f4\u07f5]", re.UNICODE)),
                ('Word', (ur"(\w[\u0300\u0301\u0302\u030c\u0308\u07eb\u07ec\u07ed\u07ee\u07ef\u07f0\u07f1\u07f2\u07f3\u07f6\u07fa-]{0,2})+", re.UNICODE)),
                ('BOM', (u'\ufeff', )),
                ('Nonword', (r'\W', re.UNICODE)),
                ]
        
        self.dan = [
                ('Comment', (u'<c>.*?</c>', re.DOTALL)),
                ('Comment', (u'<sp>.*?</sp>',)),
                ('SentPunct', (u'<st>',)),
                ('SentPunct', (u'([.!?]+(?=[\s\n\u200f])|:(?=\s*\n))', re.UNICODE)),
                ('SentPunct', (u'(?<=[.!?])\s*[»›”]+', re.UNICODE)),
                ('Punct', (u'([:;,(){}]+)', re.UNICODE)),
                ('Tag', (u'<.*?>',)),
                ('Par', (u'(\r?\n){2,}',)),
                ('NL', (u'[\r\n]',)),
                ('Space', (u'\s+', re.UNICODE)),
                ('Cardinal', (u'(\d([-.,:]\d)?)+', re.UNICODE)),
                ('Word', (u'(\w\.){2,}', re.UNICODE)),
                ('Word', (u"[=\"'‘-]?[\w\u0300\u0301\u0302\u0304\u0308\u030b\u030f]+[=\"'‘-]?", re.UNICODE)),
                ('BOM', (u'\ufeff', )),
                ('Nonword', (u'\W', re.UNICODE)),
        ]

        self._methods = {
            "bamana": self.bamana,
            "dan": self.dan,
            "default": self.bamana
        }
        self.methods = self._methods.keys()

    def get(self, method):
        return self._methods[method]

