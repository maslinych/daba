#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import codecs
import formats
import xml.etree.ElementTree as e

class SHXmlWriter(object):
    def __init__(self, (metadata, para), filename, encoding="utf-8"):
        self.encoding = encoding
        self.metadata = dict(metadata)
        self.para = para
        self.filename = filename
        self.depth = 0

        def get_meta(field):
            try:
                return self.metadata[field]
            except (KeyError):
                return ''
        self.textid = os.path.basename(self.filename)
        root = e.Element('document')
        head = e.SubElement(root, 'interlinear-text')
        head.tail = '\n'
        textid = e.SubElement(head, 'item', {'type': 'id', 'lang': 'en'})
        textid.text = self.textid
        textid.tail = '\n'
        familyru = e.SubElement(head, 'item', {'type': 'family', 'lang': 'ru'})
        familyru.text = u'Манде'
        familyru.tail = '\n'
        languageru = e.SubElement(head, 'item', {'type': 'language', 'lang': 'ru'})
        languageru.text = u'Бамана'
        languageru.tail = '\n'
        dialectru = e.SubElement(head, 'item', {'type': 'dialect', 'lang': 'ru'})
        dialectru.text = u'Бамако'
        dialectru.tail = '\n'
        familyen = e.SubElement(head, 'item', {'type': 'family', 'lang': 'en'})
        familyen.text = 'Mande'
        familyen.tail = '\n'
        languageen = e.SubElement(head, 'item', {'type': 'language', 'lang': 'en'})
        languageen.text = 'Bambara'
        languageen.tail = '\n'
        dialecten = e.SubElement(head, 'item', {'type': 'dialect', 'lang': 'en'})
        dialecten.text = 'Bamako'
        dialecten.tail = '\n'
        date = e.SubElement(head, 'item', {'type': 'dateofrecording', 'lang': 'en'})
        date.text = get_meta('source:date')
        date.tail = '\n'
        date = e.SubElement(head, 'item', {'type': 'place', 'lang': 'en'})
        date.text = get_meta('source:address')
        date.tail = '\n'
        

        title = e.SubElement(head, 'item', {'type': 'title', 'lang': 'en'})
        try:
            title.text = self.metadata['text:title']
        except (KeyError):
            title.text = self.textid
        title.tail = '\n'
        for (name, content) in metadata:
            md = e.SubElement(head, 'item', {'type': name})
            md.text = content
            md.tail = '\n'

        body = e.SubElement(head, 'paragraphs')
        body.tail = '\n'


        for (pn, para) in enumerate(self.para):
            par = e.SubElement(body, 'paragraph')
            par.tail = '\n'
            for (sn, (senttoken, sentannot)) in enumerate(para):
                ph = e.SubElement(par, 'phrases')
                ph.tail = '\n'
                st = e.SubElement(ph, 'phrase')
                st.tail = '\n'
                ref = e.SubElement(st, 'item', {'type': 'ref', 'lang': 'en'})
                ref.text = u'-'.join([title.text, unicode(pn), unicode(sn)])
                ref.tail = '\n'
                nt = e.SubElement(st,'item', {'type': 'nt', 'lang': 'bam'})
                nt.text = senttoken.value
                nt.tail = '\n'

                def morph_to_xml(ms, morph):
                    m = e.SubElement(ms, 'morph')
                    mb = e.SubElement(m, 'item', {'type': 'mb', 'lang': 'bam'})
                    mb.text = morph.form
                    mb.tail = '\n'
                    ps = e.SubElement(m, 'item', {'type': 'ps', 'lang': 'en'})
                    ps.text = u'/'.join(morph.ps)
                    ps.tail = '\n'
                    ge = e.SubElement(m, 'item', {'type': 'ge', 'lang': 'en'})
                    ge.text = morph.gloss
                    ge.tail = '\n'

                annot = e.SubElement(st, 'words')
                annot.tail = '\n'
                for (toktype, tokvalue) in sentannot:
                    if toktype in ['w']:
                        sourceform, stage, glosslist = tokvalue
                        w = e.SubElement(annot, 'word')
                        w.tail = '\n'
                        # FIXME: format doesn't support ambiguity, always take first gloss
                        gloss = glosslist[0]
                        wtext = e.SubElement(w, 'item', {'type': 'txt', 'lang': 'bam'})
                        wtext.text = gloss.form
                        wtext.tail = '\n'
                        ms = e.SubElement(w, 'morphemes')
                        ms.tail = '\n'
                        if not gloss.ps or not gloss.gloss and gloss.morphemes:
                            for morph in gloss.morphemes:
                                morph_to_xml(ms, morph)
                        else:
                            morph_to_xml(ms, gloss)


        self.xml = root

    def write(self):
        e.ElementTree(self.xml).write(self.filename, encoding=self.encoding, xml_declaration=True)


infile = sys.argv[1]
outfile = sys.argv[2]

reader = formats.HtmlReader(infile)
SHXmlWriter((reader.metadata, reader.glosses), outfile).write()
