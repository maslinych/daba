#!/usr/bin/python
# -*- encoding: utf-8 -*-

import re
from orthograph import detone
import unicodedata

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

    next = 1
    if len(struct) > 1:
        if unicodedata.category(struct[next]) == 'Mn':
            #?`
            segstring = appendtoall(segstring, ['0'])
            if len(struct) > 2:
                next = 2
            else:
                return segstring
        if struct[0] in vowels:
            # v...
            if struct[0] == struct[next]:
                # vv
                return split(struct[next:], appendtoall(segstring, ['0']))
            elif len(struct) == next+1:
                # v?$
                if struct[next] in u'n':
                    # -vn$
                    return appendtoall(segstring, ['0'])
                else:
                    # v-[^n]$
                    return appendtoall(segstring, ['1'])
            else:
                if struct[next] in u'n':
                    if struct[next+1] in consonants:
                        # v-nc | vn-c
                        return split(struct[next+1:], appendtoall(segstring, ['01', '10']))
                    elif struct[next+1] in vowels:
                        # v-nv
                        return split(struct[next+1:], appendtoall(segstring, ['10']))
                    else:
                        # vn-[^cv]
                        return split(struct[next+1:], appendtoall(segstring, ['01']))
                else:
                    # v-[^n]
                    return split(struct[next:], appendtoall(segstring, ['1']))
        else:
            # [^v]
            return split(struct[next:], appendtoall(segstring, ['0']))
    else:
        # $
        return segstring

def syllabify(word):
    nword = unicodedata.normalize('NFD', word)
    seglist = [segment(nword, seg) for seg in split(nword, [''])]
    return [[unicodedata.normalize('NFC', sy) for sy in w] for w in seglist]

