#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import formats
from orthography import detone

infile = sys.argv[1]

reader = formats.HtmlReader(infile)

print "<text ",
for name,value in reader.metadata:
    print u'{0}="{1}"'.format(name, value).encode("utf-8"),
print ">"

for par in reader.glosses:
    print "<p>"
    for sent,annot in par:
        print "<sent>"
        #print u'<sent source="{0}">'.format(sent).encode('utf-8')
        for token in annot:
            gt = formats.GlossToken(token)
            print u"{0}\t".format(gt.token).encode('utf-8'),
            if gt.type == 'w':
                print u"\t".join([u'|'.join(set(s)) for s in zip(*[(g.form, '|'.join(g.ps), g.gloss) for g in gt.glosslist])]).encode('utf-8'),
                print u"\t{0}".format(u'|'.join(set([detone(g.form).lower() for g in gt.glosslist]))).encode('utf-8')
            else:
                print u"\t".join([gt.token, gt.type, gt.token, gt.token]).encode('utf-8')
        print "</sent>"
    print "</p>"

print "</text>"




