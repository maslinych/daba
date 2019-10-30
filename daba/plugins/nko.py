#!/usr/bin/env python3
# -*- coding: utf8 -*-

from . import OrthographyConverter
import re

debug = False

class NkoToLatin(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'nko'
        self.desc = 'Convertor from NKO to latin script'

    def convert(self, token):
        """
        Main NKO>latin conversion method
        """
        
        if re.search("[a-zA-Z]", token):
            return [token]


        w = token
        if debug:
            print "NKO", w.encode("utf-8"), 
    ### FOREIGN sounds with diacritics:
        w = w.replace(u'\u07d6\u07ed', ur"z")
        w = w.replace(u'\u07db\u07ed', ur"S")   ### SH
        w = w.replace(u'\u07dc\u07ed', ur"g")
        w = w.replace(u'\u07dd\u07ed', ur"v")
        w = w.replace(u'\u07d8\u07ed', ur"D")   ### D.
        w = w.replace(u'\u07e4\u07ed', ur"Q")   ### H.
        w = w.replace(u'\u07d7\u07ed', ur"J")   ### C.
        w = w.replace(u'\u07de\u07ed', ur"x")   ### K.
        w = w.replace(u'\u07d5\u07ed', ur"T")   ### T.
        
        w = w.replace(u'\u07ca\u07f3', ur"A")   ### A"
        w = w.replace(u'\u07db\u07f3', ur"F")   ### S"
        w = w.replace(u'\u07d6\u07f3', ur"Z")   ### J"
        
        w = w.replace(u'\u07db\u07eb', ur"C")   ### S=
        w = w.replace(u'\u07de\u07eb', ur"q")   ### K=

        w = w.replace(u'\u07f3', ur"\u0308")
        w = w.replace(u'\u07f6', ur"o")
        w = w.replace(u'\u07cb\u0623', ur"{")
        w = w.replace(u'\u07cb\u0625', ur"}")	

    ### VOWELS:
        w = w.replace(u'\u07ca', ur"a")
        w = w.replace(u'\u07cb', ur"e")
        w = w.replace(u'\u07cc', ur"i")
        w = w.replace(u'\u07cd', ur"H")
        w = w.replace(u'\u07ce', ur"u")
        w = w.replace(u'\u07cf', ur"o")
        w = w.replace(u'\u07d0', ur"O")
    ### SYLLABIC N
        w = w.replace(u'\u07d2', ur"N")

    ### CONSONANTS:
        w = w.replace(u'\u07d3', ur"b")
        w = w.replace(u'\u07d4', ur"p")
        w = w.replace(u'\u07d5', ur"t")
        w = w.replace(u'\u07d6', ur"j")
        w = w.replace(u'\u07d7', ur"c")
        w = w.replace(u'\u07d8', ur"d")
        w = w.replace(u'\u07d9', ur"r")
        w = w.replace(u'\u07da', ur"R")
        w = w.replace(u'\u07db', ur"s")
        w = w.replace(u'\u07dc', ur"G")
        w = w.replace(u'\u07dd', ur"f")
        w = w.replace(u'\u07de', ur"k")
        w = w.replace(u'\u07df', ur"l")
        w = w.replace(u'\u07e0', ur"n")   # Na woloso
        w = w.replace(u'\u07e1', ur"m")
        w = w.replace(u'\u07e2', ur"Y")   # Nya
        w = w.replace(u'\u07e3', ur"n")
        w = w.replace(u'\u07e4', ur"h")
        w = w.replace(u'\u07e5', ur"w")
        w = w.replace(u'\u07e6', ur"y")
        w = w.replace(u'\u07e7', ur"y")   # Nya woloso

    ### APOSTROPHES:
        w = w.replace(u'\u07f4', ur"’")
        w = w.replace(u'\u07f5', ur"‘")



    ### PUNCTUATION:
        w = w.replace(u'\u060c', ur",")  # Arabic comma
        w = w.replace(u'\u061f', ur"?")  # Arabic question mark
        w = w.replace(u'؛', ur";")
        w = w.replace(u'\u07fa', ur"-")
        w = w.replace(u'\u066a', ur"%")	

    ### MARKING HIGH TONE:
        w = re.sub(u'(a|e|H|i|o|O|u|N)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q|-)', ur"\1\u0301\2", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)(a|e|H|i|o|O|u|N)', ur"\1\u0301\2", w)
        w = re.sub(u'(a|e|H|i|o|O|u)$', ur"\1\u0301`", w)
        w = re.sub(u'N$', ur"N\u0301", w)


        w = re.sub(u'(a|e|H|i|o|O|u)\u07f2(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q|-)', ur"\1\u0301X\2", w)
    ##w = re.sub(u'(a|e|H|i|o|O|u)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)\u07f2', ur"\1\u0301n\3", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07f2$', ur"\1\u0301n`", w)


    ### MOVING THE NASALIZATION MARK AFTER THE TONE MARK:
        w = re.sub(u'\u07f2(\u07eb|\u07ec|\u07ed|\u07ee|\u07ef|\u07f0|\u07f1)', ur"\1\u07f2", w)	
        w = re.sub(u'(a|e|H|i|o|O|u)\u07f2\u07eb$', ur"\1\u0301n", w)

    ### RAISING TONES AT THE END OF A WORD
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ed$', ur"\1\u030c`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ed\u07f2$', ur"\1\u030cn`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07f1$', ur"\1\u030c\1`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07f1\u07f2$', ur"\1\u030c\1n`", w)

    ### TONES (short):
        w = re.sub(u'\u07eb', ur"\u0301", w)
        w = re.sub(u'\u07ec', ur"\u0300", w)
        w = re.sub(u'\u07ed', ur"\u030c", w)

    ### GBARALI:
        w = re.sub(u'(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(a|e|H|i|o|O|u|N)(\u0301|\u0300|\u030c)', ur"\1\3\4\2\3\4", w)

    ### GBARALI for tone apostrophes:
        w = w.replace(u'a\u0301lm[‘’]', ur"a\u0301la\u0301m'")
        w = w.replace(u'bd[‘’]', ur"ba\u0301d'")
        w = w.replace(u'br[‘]', ur"ba\u0301r'")
        w = w.replace(u'dO\u0301tl[’]', ur"dO\u0301ta\u0301l'")
        w = w.replace(u'fd[’]', ur"fd'") # any vowel possible: a e u
        w = w.replace(u'fn[’]', ur"fa\u0301n'")
        w = w.replace(u'fr[‘’]', ur"fa\u0301r'")
        w = w.replace(u'Gr[‘’]', ur"Ga\u0300r'")
        w = w.replace(u'hákílímy[’]', ur"hákílímáy'")
        w = w.replace(u'hl[’]', ur"ha\u0301l'")
        w = w.replace(u'jk[‘]', ur"ja\u0301k'")
        w = w.replace(u'kf[’]', ur"ka\u0301f'")
        w = w.replace(u'kn[‘’]', ur"ka\u0301n'")
        w = w.replace(u'kY[‘]', ur"kE\u0301Y'")
        w = w.replace(u'látd[‘]', ur"látE\u0300d'")
        w = w.replace(u'dm[’]', ur"dE\u0300m'")
        w = w.replace(u'mákb[’]', ur"mákáb'")
        w = w.replace(u'mákl[’]', ur"mákíl'")
        w = w.replace(u'nr[’]', ur"na\u0301r'")
        w = w.replace(u'Yáml[’]', ur"Yámál'")
        w = w.replace(u'sr[‘]', ur"sa\u0300r'")
        w = w.replace(u'tl[’]', ur"ta\u0301l'")
        w = w.replace(u'td[‘’]', ur"tE\u0300d'")
        w = w.replace(u'wl[‘’]', ur"wa\u0301l'")
        w = w.replace(u'yd[‘]', ur"ya\u0300d'")
        
        w = re.sub(u'(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)[‘’]', ur"\1#\2'", w)
    ##############################################
    ### Incorrect use of ‘ instead of dagbasinna:
        w = re.sub(u'(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)‘(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)', ur"\1\2", w)
        w = w.replace("\u07d1", "")
        w = w.replace(u'X', ur"n")

    ### TONES (long):
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ee\u07f2', ur"\1\u0301\1n`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ee', ur"\1\u0301\1`", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07ef', ur"\1\u0301\1", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07f0', ur"\1\u0300\1", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07f1', ur"\1\u030c\1", w)

    ### REMOVE flowting low tone from "i" and "n" pronouns:
        w = re.sub(u'\b([iN])\u0301`', ur"\1\u0301", w)	
        
   ### NUMERALS:
        w = w.replace(u'\u07c0', ur"0")
        w = w.replace(u'\u07c1', ur"1")
        w = w.replace(u'\u07c2', ur"2")
        w = w.replace(u'\u07c3', ur"3")
        w = w.replace(u'\u07c4', ur"4")
        w = w.replace(u'\u07c5', ur"5")
        w = w.replace(u'\u07c6', ur"6")
        w = w.replace(u'\u07c7', ur"7")
        w = w.replace(u'\u07c8', ur"8")
        w = w.replace(u'\u07c9', ur"9")
        w = w.replace(u'(\d)\u07f2', ur"\1nan")

    ### NASALIZATION MARK:    
        w = w.replace(u'\u07f2', ur"n")

    ##  s/[-,;:\.\x84\x85\"\x91-\x94\xAB\xBB\x96\x97\(\)\?\!]//g;

        w = w.replace(u'H', ur"ɛ")
        w = w.replace(u'O', ur"ɔ")
        w = w.replace(u'Y', ur"ɲ")
        w = w.replace(u'R', ur"rr")
        w = w.replace(u'G', ur"gb")
        w = w.replace(u'S', ur"sh")   # sh
        w = w.replace(u'D', ur"d\u0323")   ### D.
        w = w.replace(u'Q', ur"\u0127")    ### H.
        w = w.replace(u'J', ur"\u0292")    ### C. = zh
        w = w.replace(u'A', ur"\u0295")    ### A"
        w = w.replace(u'F', ur"\u03b8")    ### S"
        w = w.replace(u'T', ur"t\u0323")   ### J"
        w = w.replace(u'Z', ur"z\u0323")   ### J"
        w = w.replace(u'C', ur"s\u0323")   ### S=
        w = w.replace(u'\u07f8', ur",")
        w = w.replace(u'\u07f9', ur"!")
        w = re.sub(u'[‘]', ur"`", w)
        w = re.sub(u'[’]', ur"'", w)
        w = w.replace('_', '')
        w = w.replace(u'\u0640', '')
        w = w.replace(u'N', u'n')
        w = re.sub(ur'^i\u0301`$', ur'i\u0301', w)
        
        if debug:
            print "LAT", w.encode("utf-8"),
        w = self.normalize_tones(w)

        if debug:
            print "TNL", w.encode("utf-8")
        return [w]

    def normalize_tones(self, word):
        """Replace surface tones resulting from the plain NKO>latin conversion with deep (lexical) tones"""
        word = word.replace(u'\u030c', ur'\u0300')
        if u'N\u0301' in word:
            Nlow = 0
        elif u'N\u0300' in word:
            Nlow = 1
        else:
            Nlow = 3

        pieces = word.split(u'N\u0301')
        outword = []
        for piece in pieces:
            piece = re.sub(u'(?P<t>[\u0300\u0301])', u'\g<t>|', piece)
            piece = re.sub(u'(?P<v>[aeiouɛɔ])(?P<t>[\u0300\u0301])\|(?P=v)', u'\g<v>\g<t>\g<v>|', piece)

            syllables = piece.split('|')
            if u'\u0300' in syllables[0]:
                lowtone = 1
            else:
                lowtone = 0

            index = 0
            if lowtone == 1:
                for syl in syllables[1:]:
                    index += 1
                    syllables[index] = re.sub(u'[\u0300\u0301]', u'', syl)
            else:
                for syl in syllables[1:]:
                    index += 1
                    if lowtone == 0 and u'\u0301' in syl:
                        syllables[index] = syl.replace(u'\u0301', u'')
                    elif lowtone == 0 and u'\u0300' in syl:
                        lowtone = 2
                    elif lowtone == 2:
                        syllables[index] = re.sub(u'[\u0301\u0300]', u'', syl)
            outword.append(u''.join(syllables))

        if Nlow == 0:
            Njoiner = u'N\u0301'
        elif Nlow == 1:
            Njoiner = u'N\u0300'
        else:
            Njoiner = u'N'

        finalword = Njoiner.join(outword)
        finalword = re.sub(u'N\u0301ta\u0301(`?)', u'Ntan\1', finalword)
        return finalword





