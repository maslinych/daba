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
            print("NKO", w, )
    ### FOREIGN sounds with diacritics:
        w = w.replace(u'\u07d6\u07ed', r"z")
        w = w.replace(u'\u07db\u07ed', r"S")   ### SH
        w = w.replace(u'\u07dc\u07ed', r"g")
        w = w.replace(u'\u07dd\u07ed', r"v")
        w = w.replace(u'\u07d8\u07ed', r"D")   ### D.
        w = w.replace(u'\u07e4\u07ed', r"Q")   ### H.
        w = w.replace(u'\u07d7\u07ed', r"J")   ### C.
        w = w.replace(u'\u07de\u07ed', r"x")   ### K.
        w = w.replace(u'\u07d5\u07ed', r"T")   ### T.
        
        w = w.replace(u'\u07ca\u07f3', r"A")   ### A"
        w = w.replace(u'\u07db\u07f3', r"F")   ### S"
        w = w.replace(u'\u07d6\u07f3', r"Z")   ### J"
        
        w = w.replace(u'\u07db\u07eb', r"C")   ### S=
        w = w.replace(u'\u07de\u07eb', r"q")   ### K=

        w = w.replace(u'\u07f3', r"\u0308")
        w = w.replace(u'\u07f6', r"o")
        w = w.replace(u'\u07cb\u0623', r"{")
        w = w.replace(u'\u07cb\u0625', r"}")

    ### VOWELS:
        w = w.replace(u'\u07ca', r"a")
        w = w.replace(u'\u07cb', r"e")
        w = w.replace(u'\u07cc', r"i")
        w = w.replace(u'\u07cd', r"H")
        w = w.replace(u'\u07ce', r"u")
        w = w.replace(u'\u07cf', r"o")
        w = w.replace(u'\u07d0', r"O")
    ### SYLLABIC N
        w = w.replace(u'\u07d2', r"N")

    ### CONSONANTS:
        w = w.replace(u'\u07d3', r"b")
        w = w.replace(u'\u07d4', r"p")
        w = w.replace(u'\u07d5', r"t")
        w = w.replace(u'\u07d6', r"j")
        w = w.replace(u'\u07d7', r"c")
        w = w.replace(u'\u07d8', r"d")
        w = w.replace(u'\u07d9', r"r")
        w = w.replace(u'\u07da', r"R")
        w = w.replace(u'\u07db', r"s")
        w = w.replace(u'\u07dc', r"G")
        w = w.replace(u'\u07dd', r"f")
        w = w.replace(u'\u07de', r"k")
        w = w.replace(u'\u07df', r"l")
        w = w.replace(u'\u07e0', r"n")   # Na woloso
        w = w.replace(u'\u07e1', r"m")
        w = w.replace(u'\u07e2', r"Y")   # Nya
        w = w.replace(u'\u07e3', r"n")
        w = w.replace(u'\u07e4', r"h")
        w = w.replace(u'\u07e5', r"w")
        w = w.replace(u'\u07e6', r"y")
        w = w.replace(u'\u07e7', r"y")   # Nya woloso

    ### APOSTROPHES:
        w = w.replace(u'\u07f4', r"’")
        w = w.replace(u'\u07f5', r"‘")



    ### PUNCTUATION:
        w = w.replace(u'\u060c', r",")  # Arabic comma
        w = w.replace(u'\u061f', r"?")  # Arabic question mark
        w = w.replace(u'؛', r";")
        w = w.replace(u'\u07fa', r"-")
        w = w.replace(u'\u066a', r"%")

    ### MARKING HIGH TONE:
        w = re.sub(u'(a|e|H|i|o|O|u|N)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q|-)', r"\1\u0301\2", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)(a|e|H|i|o|O|u|N)', r"\1\u0301\2", w)
        w = re.sub(u'(a|e|H|i|o|O|u)$', r"\1\u0301`", w)
        w = re.sub(u'N$', r"N\u0301", w)


        w = re.sub(u'(a|e|H|i|o|O|u)\u07f2(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q|-)', r"\1\u0301X\2", w)
    ##w = re.sub(u'(a|e|H|i|o|O|u)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)\u07f2', r"\1\u0301n\3", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07f2$', r"\1\u0301n`", w)


    ### MOVING THE NASALIZATION MARK AFTER THE TONE MARK:
        w = re.sub(u'\u07f2(\u07eb|\u07ec|\u07ed|\u07ee|\u07ef|\u07f0|\u07f1)', r"\1\u07f2", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07f2\u07eb$', r"\1\u0301n", w)

    ### RAISING TONES AT THE END OF A WORD
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ed$', r"\1\u030c`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ed\u07f2$', r"\1\u030cn`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07f1$', r"\1\u030c\1`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07f1\u07f2$', r"\1\u030c\1n`", w)

    ### TONES (short):
        w = re.sub(u'\u07eb', r"\u0301", w)
        w = re.sub(u'\u07ec', r"\u0300", w)
        w = re.sub(u'\u07ed', r"\u030c", w)

    ### GBARALI:
        w = re.sub(u'(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(a|e|H|i|o|O|u|N)(\u0301|\u0300|\u030c)', r"\1\3\4\2\3\4", w)

    ### GBARALI for tone apostrophes:
        w = w.replace(u'a\u0301lm[‘’]', r"a\u0301la\u0301m'")
        w = w.replace(u'bd[‘’]', r"ba\u0301d'")
        w = w.replace(u'br[‘]', r"ba\u0301r'")
        w = w.replace(u'dO\u0301tl[’]', r"dO\u0301ta\u0301l'")
        w = w.replace(u'fd[’]', r"fd'") # any vowel possible: a e u
        w = w.replace(u'fn[’]', r"fa\u0301n'")
        w = w.replace(u'fr[‘’]', r"fa\u0301r'")
        w = w.replace(u'Gr[‘’]', r"Ga\u0300r'")
        w = w.replace(u'hákílímy[’]', r"hákílímáy'")
        w = w.replace(u'hl[’]', r"ha\u0301l'")
        w = w.replace(u'jk[‘]', r"ja\u0301k'")
        w = w.replace(u'kf[’]', r"ka\u0301f'")
        w = w.replace(u'kn[‘’]', r"ka\u0301n'")
        w = w.replace(u'kY[‘]', r"kE\u0301Y'")
        w = w.replace(u'látd[‘]', r"látE\u0300d'")
        w = w.replace(u'dm[’]', r"dE\u0300m'")
        w = w.replace(u'mákb[’]', r"mákáb'")
        w = w.replace(u'mákl[’]', r"mákíl'")
        w = w.replace(u'nr[’]', r"na\u0301r'")
        w = w.replace(u'Yáml[’]', r"Yámál'")
        w = w.replace(u'sr[‘]', r"sa\u0300r'")
        w = w.replace(u'tl[’]', r"ta\u0301l'")
        w = w.replace(u'td[‘’]', r"tE\u0300d'")
        w = w.replace(u'wl[‘’]', r"wa\u0301l'")
        w = w.replace(u'yd[‘]', r"ya\u0300d'")
        
        w = re.sub(u'(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)[‘’]', r"\1#\2'", w)
    ##############################################
    ### Incorrect use of ‘ instead of dagbasinna:
        w = re.sub(u'(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)‘(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)', r"\1\2", w)
        w = w.replace("\u07d1", "")
        w = w.replace(u'X', r"n")

    ### TONES (long):
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ee\u07f2', r"\1\u0301\1n`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ee', r"\1\u0301\1`", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07ef', r"\1\u0301\1", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07f0', r"\1\u0300\1", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07f1', r"\1\u030c\1", w)

    ### REMOVE flowting low tone from "i" and "n" pronouns:
        w = re.sub(u'\b([iN])\u0301`', r"\1\u0301", w)
        
   ### NUMERALS:
        w = w.replace(u'\u07c0', r"0")
        w = w.replace(u'\u07c1', r"1")
        w = w.replace(u'\u07c2', r"2")
        w = w.replace(u'\u07c3', r"3")
        w = w.replace(u'\u07c4', r"4")
        w = w.replace(u'\u07c5', r"5")
        w = w.replace(u'\u07c6', r"6")
        w = w.replace(u'\u07c7', r"7")
        w = w.replace(u'\u07c8', r"8")
        w = w.replace(u'\u07c9', r"9")
        w = w.replace(u'(\d)\u07f2', r"\1nan")

    ### NASALIZATION MARK:    
        w = w.replace(u'\u07f2', r"n")

    ##  s/[-,;:\.\x84\x85\"\x91-\x94\xAB\xBB\x96\x97\(\)\?\!]//g;

        w = w.replace(u'H', r"ɛ")
        w = w.replace(u'O', r"ɔ")
        w = w.replace(u'Y', r"ɲ")
        w = w.replace(u'R', r"rr")
        w = w.replace(u'G', r"gb")
        w = w.replace(u'S', r"sh")   # sh
        w = w.replace(u'D', r"d\u0323")   ### D.
        w = w.replace(u'Q', r"\u0127")    ### H.
        w = w.replace(u'J', r"\u0292")    ### C. = zh
        w = w.replace(u'A', r"\u0295")    ### A"
        w = w.replace(u'F', r"\u03b8")    ### S"
        w = w.replace(u'T', r"t\u0323")   ### J"
        w = w.replace(u'Z', r"z\u0323")   ### J"
        w = w.replace(u'C', r"s\u0323")   ### S=
        w = w.replace(u'\u07f8', r",")
        w = w.replace(u'\u07f9', r"!")
        w = re.sub(u'[‘]', r"`", w)
        w = re.sub(u'[’]', r"'", w)
        w = w.replace('_', '')
        w = w.replace(u'\u0640', '')
        w = w.replace(u'N', u'n')
        w = re.sub(r'^i\u0301`$', r'i\u0301', w)
        
        if debug:
            print("LAT", w,)
        w = self.normalize_tones(w)

        if debug:
            print("TNL", w)
        return [w]

    def normalize_tones(self, word):
        """Replace surface tones resulting from the plain NKO>latin conversion with deep (lexical) tones"""
        word = word.replace(u'\u030c', r'\u0300')
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





