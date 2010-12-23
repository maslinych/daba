#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Manual disambiguation editor
#
# Copyright (C) 2010  Kirill Maslinsky <kirill@altlinux.org>
#
# This file is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
from ntgloss import Gloss
import xml.etree.cElementTree as e

#xgloss = e.fromstring(html)

# p
#   sent
#       annot
#               c|w
#                       m|lemma var>>
def elem_to_gloss(xgloss):
    morphemes = []
    if xgloss.attrib['class'] in ['w', 'm', 'lemma var']:
        form = xgloss.text
        for i in xgloss.getchildren():
            if i.attrib['class'] == 'ps':
                ps = set(i.text.split('/'))
            elif i.attrib['class'] == 'gloss':
                gloss = i.text
            elif i.attrib['class'] == 'm':
                morphemes.append(elem_to_gloss(i))
    elif xgloss.attrib['class'] in ['c']:
        form = xgloss.text
        ps = set(['PUNCT'])
        gloss = ''
    return Gloss(form, ps, gloss, tuple(morphemes))

def parse_sent(sent):
    text = sent.text
    annot = []
    for span in sent.findall('span'):
        if span.attrib['class'] == 'annot':
            for w in span.findall('span'):
                if w.attrib['class'] in ['w', 'c']:
                    glosslist = []
                    glosslist.append(elem_to_gloss(w))
                    for var in w.findall('span'):
                        if var.attrib['class'] == 'lemma var':
                            glosslist.append(elem_to_gloss(var))
                    annot.append(glosslist)
    return (text, annot)


