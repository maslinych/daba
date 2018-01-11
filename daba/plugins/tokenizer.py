#!/usr/bin/env python
# coding: utf-8
import re

specs = [
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
