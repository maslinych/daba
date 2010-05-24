#!/usr/bin/python
# -*- encoding: utf-8 -*-

import re
from orthograph import detone

#consonants = 'klbmsrdtgfjchzpɲŋ'
#literals = 'ywrln'
vowels = u'aiɛɔoeu'
consonants = u'klbsrdtgfjchzp'

def segment(text, segs):
    words = []
    last = 0
    for i in range(len(segs)):
        if segs[i] == '1':
            words.append(text[last:i+1])
            last = i+1
    words.append(text[last:])
    return words

def split(struct, segstring):
    'wordform -> [segstring]'
    def appendtoall(res, list):
        return [res[k] + b for k in range(len(res)) for b in list]
    if len(struct) > 1:
        if struct[0] in vowels:
            # v...
            if struct[0] == struct[1]:
                # vv
                return split(struct[1:], appendtoall(segstring, ['0']))
            elif len(struct) == 2:
                # v?$
                if struct[1] in u'n':
                    # -vn$
                    return appendtoall(segstring, ['0'])
                else:
                    # v-[^n]$
                    return appendtoall(segstring, ['1'])
            else:
                if struct[1] in u'n':
                    if struct[2] in consonants:
                        # v-nc | vn-c
                        return split(struct[2:], appendtoall(segstring, ['01', '10']))
                    else:
                        # v-n[^c]
                        return split(struct[2:], appendtoall(segstring, ['10']))
                else:
                    # v-[^n]
                    return split(struct[1:], appendtoall(segstring, ['1']))
        else:
            # [^v]
            return split(struct[1:], appendtoall(segstring, ['0']))
    else:
        # $
        return segstring

def syllabify(word):
    return [segment(word, seg) for seg in split(word, [''])]

