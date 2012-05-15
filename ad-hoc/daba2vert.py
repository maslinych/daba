#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import formats
from orthography import detone


infile = sys.argv[1]
tonal = bool(int(sys.argv[2]))

reader = formats.HtmlReader(infile)

print "<doc ",
print u'id="{0}"'.format(os.path.basename(infile)).encode('utf-8'),
metad = dict(reader.metadata)
try:
    genres = metad['text:genre'].split(';')
    hgenres = [g.split(' : ')[0] for g in genres] + genres
    hgenres.sort()
    metad['text:genre'] = u';'.join(hgenres)
    print u'text_genre="{0}"'.format(metad['text:genre']).encode('utf-8'),
except (KeyError):
    print 'text_genre="UNDEF"',
try:
    print u'text_title="{0}"'.format(metad['text:title']).encode('utf-8'),
except (KeyError):
    print 'text_title="UNDEF"',
print ">"

for par in reader.glosses:
    print "<p>"
    for sent,annot in par:
        print "<s>"
        for token in annot:
            gt = formats.GlossToken(token)
            print u"{0}\t".format(gt.token).encode('utf-8'),
            if gt.type == 'w':
                if tonal:
                    get_lemma = lambda x: ''.join(c for c in x if c not in '.')
                else:
                    get_lemma = lambda x: detone(''.join(c for c in x if c not in '.')
)

                lemmas = []
                tags = set([])
                glosses = []
                for g in gt.glosslist:
                    if not (g.gloss and g.ps) and g.morphemes:
                        for m in g.morphemes:
                            if 'mrph' not in m.ps:
                                lemmas.append(get_lemma(m.form))
                                tags = tags.union(m.ps)
                            glosses.append(m.gloss)
                    else:
                        lemmas.append(get_lemma(g.form))
                        tags = tags.union(g.ps)
                        glosses.append(g.gloss)
                
                print u"\t".join([u'|'.join(filter(None, set(s))) for s in [lemmas, tags, glosses]]).encode('utf-8')
            else:
                print u"\t".join([gt.token, gt.type, gt.token]).encode('utf-8')
        print "</s>"
    print "</p>"

print "</doc>"




