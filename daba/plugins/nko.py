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

        w = token
        
        # if token.type != 'Word':
        #     w = w.replace('\u060c', ',')
        #     w = w.replace('\u200f', '')
        #     return [w]
            
        if re.search("[a-zA-Z]", w):
            return [w]


        if debug:
            print("NKO", w, )
    ### FOREIGN sounds with diacritics:    
    #   07ed=short rising tone (dot above)  07f3=double dot above  07eb= short high tone (bar above)
        w = w.replace('\u07d6\u07ed', r"z")
        w = w.replace('\u07db\u07ed', r"S")   ### SH
        w = w.replace('\u07dc\u07ed', r"g")
        w = w.replace('\u07dd\u07ed', r"v")
        w = w.replace('\u07d8\u07ed', r"D")   ### D.
        w = w.replace('\u07e4\u07ed', r"Q")   ### H.
        w = w.replace('\u07d7\u07ed', r"J")   ### C. CHA+short rising tone
        w = w.replace('\u07de\u07ed', r"x")   ### K.
        w = w.replace('\u07d5\u07ed', r"T")   ### T.
        
        w = w.replace('\u07ca\u07f3', r"A")   ### A"
        w = w.replace('\u07db\u07f3', r"F")   ### S"
        w = w.replace('\u07d6\u07f3', r"Z")   ### J"
        
        w = w.replace('\u07db\u07eb', r"C")   ### S=
        w = w.replace('\u07de\u07eb', r"q")   ### K=

        w = w.replace('\u07f3', "\u0308")     # Double dot above -> ̈   Combining Diaeresis (U+0308)

        w = w.replace('\u07f6', r"o")         #    ߶ N'Ko OO dennen
        w = w.replace('\u07cb\u0623', r"{")   #    ߋ N'ko EE + أ Arabic Letter Alef With Hamza Above (U+0623)
        w = w.replace('\u07cb\u0625', r"}")   #    ߋ N'ko EE + إ Arabic Letter Alef With Hamza Below (U+0625)

    ### VOWELS:
        w = w.replace('\u07ca', r"a")
        w = w.replace('\u07cb', r"e")
        w = w.replace('\u07cc', r"i")
        w = w.replace('\u07cd', r"H")  # ߍ 
        w = w.replace('\u07ce', r"u")
        w = w.replace('\u07cf', r"o")
        w = w.replace('\u07d0', r"O")
    ### SYLLABIC N
        w = w.replace('\u07d2', r"N")  # ߒ 

    ### CONSONANTS:
        w = w.replace('\u07d3', r"b")
        w = w.replace('\u07d4', r"p")
        w = w.replace('\u07d5', r"t")
        w = w.replace('\u07d6', r"j")
        w = w.replace('\u07d7', r"c")
        w = w.replace('\u07d8', r"d")
        w = w.replace('\u07d9', r"r")
        w = w.replace('\u07da', r"R")
        w = w.replace('\u07db', r"s")
        w = w.replace('\u07dc', r"G")
        w = w.replace('\u07dd', r"f")
        w = w.replace('\u07de', r"k")
        w = w.replace('\u07df', r"l")
        w = w.replace('\u07e0', r"n")   # ߠ Na woloso
        w = w.replace('\u07e1', r"m")
        w = w.replace('\u07e2', r"Y")   # ߢ Nya
        w = w.replace('\u07e3', r"n")
        w = w.replace('\u07e4', r"h")
        w = w.replace('\u07e5', r"w")
        w = w.replace('\u07e6', r"y")
        w = w.replace('\u07e7', r"y")   # ߧ Nya woloso

    ### APOSTROPHES:
        #w = w.replace('\u07f4', r"’")
        #w = w.replace('\u07f5', r"‘")
        w = w.replace('\u07f4', r"'")   # MODIFIED JJM 09/10/2024
        w = w.replace('\u07f5', r"'")   # MODIFIED JJM 09/10/2024

    ### DOUBLE PUNCTUATIONS #  MODIFIED JJM 18/10/2024 
        w = w.replace('ߵߵ', r'"')
        #w = w.replace('<<', r'«')  # this is handled in mparser sent_splitter
        #w = w.replace('>>', r'»')

    ### PUNCTUATION:
        w = w.replace('\u060c', r",")  # Arabic comma
        w = w.replace('\u061f', r"?")  # Arabic question mark
        w = w.replace('؛', r";")       # U+061B ؛ ARABIC SEMICOLON
        w = w.replace('\u07fa', r"-")  # N'Ko LAJANYALAN
        w = w.replace('\u066a', r"%")  # Arabic Percent sign ٪
        w = w.replace('\u200f', '')    # right-to-left mark
        w = w.replace('\u07f9', r"!")  # N'Ko EXLAMATION MARK
        w = w.replace(' \u07d1 ', r" ߸ ")  # erroneous use of N'ko dagbasinna as N'Ko comma (always between spaces) - JJM 19/nov/2024
        w = w.replace('\u07f8', ",")   # N'Ko COMMA ߸
        w = w.replace('\u202e', " ")   # RLO (Right-Left Override)
        # not translated : ref https://www.unicode.org/charts/PDF/U07C0.pdf
        # \07F7 NKO SYMBOL GBAKURUNEN ߷
        # \07FE NKO DOROME SIGN ߾߾
        # \07FF NKO TAMAN SIGN ߿
        # \07FD NKO DANTAYALAN ߽
        # bad idea? w = w.replace('(', "¤(¤")   # rotate parenthesis JJM 11/12/2024
        # bad idea? w = w.replace(')', "(")
        # bad idea? w = w.replace("¤(¤",")")

    ### MARKING HIGH TONE:
        w = re.sub('(a|e|H|i|o|O|u|N)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q|-)', "\\1\u0301\\2", w)
        w = re.sub('(a|e|H|i|o|O|u|N)(a|e|H|i|o|O|u|N)', "\\1\u0301\\2", w)
        w = re.sub('(a|e|H|i|o|O|u)$', "\\1\u0301`", w)
        w = re.sub('N$', "N\u0301", w)


        w = re.sub('(a|e|H|i|o|O|u)\u07f2(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q|-)', "\\1\u0301X\\2", w)
    ##w = re.sub('(a|e|H|i|o|O|u)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)\u07f2', r"\1\u0301n\3", w)
        w = re.sub('(a|e|H|i|o|O|u)\u07f2$', "\\1\u0301n`", w)


    ### MOVING THE NASALIZATION MARK AFTER THE TONE MARK:
        w = re.sub('\u07f2(\u07eb|\u07ec|\u07ed|\u07ee|\u07ef|\u07f0|\u07f1)', "\\1\u07f2", w)
        w = re.sub('(a|e|H|i|o|O|u)\u07f2\u07eb$', "\\1\u0301n", w)

    ### RAISING TONES AT THE END OF A WORD
        w = re.sub('(a|e|H|i|o|O|u)\u07ed$', "\\1\u030c`", w)
        w = re.sub('(a|e|H|i|o|O|u)\u07ed\u07f2$', "\\1\u030cn`", w)
        w = re.sub('(a|e|H|i|o|O|u)\u07f1$', "\\1\u030c\\1`", w)
        w = re.sub('(a|e|H|i|o|O|u)\u07f1\u07f2$', "\\1\u030c\\1n`", w)

    ### TONES (short):
        w = re.sub('\u07eb', "\u0301", w)
        w = re.sub('\u07ec', "\u0300", w)
        w = re.sub('\u07ed', "\u030c", w)

    ### GBARALI:
        w = re.sub('(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(a|e|H|i|o|O|u|N)(\u0301|\u0300|\u030c)', r"\1\3\4\2\3\4", w)

    ### GBARALI for tone apostrophes:
        w = re.sub('a\u0301lm[‘’]', "a\u0301la\u0301m'", w)
        w = re.sub('bd[‘’]', "ba\u0301d'", w)
        w = re.sub('br[‘]', "ba\u0301r'", w)
        w = re.sub('dO\u0301tl[’]', "dO\u0301ta\u0301l'", w)
        w = re.sub('fd[’]', "fd'", w) # any vowel possible: a e u
        w = re.sub('fn[’]', "fa\u0301n'", w)
        w = re.sub('fr[‘’]', "fa\u0301r'", w)
        w = re.sub('Gr[‘’]', "Ga\u0300r'", w)
        w = re.sub('hákílímy[’]', r"hákílímáy'", w)
        w = re.sub('hl[’]', "ha\u0301l'", w)
        w = re.sub('jk[‘]', "ja\u0301k'", w)
        w = re.sub('kf[’]', "ka\u0301f'", w)
        w = re.sub('kn[‘’]', "ka\u0301n'", w)
        w = re.sub('kY[‘]', "kE\u0301Y'", w)
        w = re.sub('látd[‘]', "látE\u0300d'", w)
        w = re.sub('dm[’]', "dE\u0300m'", w)
        w = re.sub('mákb[’]', r"mákáb'", w)
        w = re.sub('mákl[’]', r"mákíl'", w)
        w = re.sub('nr[’]', "na\u0301r'", w)
        w = re.sub('Yáml[’]', r"Yámál'", w)
        w = re.sub('sr[‘]', "sa\u0300r'", w)
        w = re.sub('tl[’]', "ta\u0301l'", w)
        w = re.sub('td[‘’]', "tE\u0300d'", w)
        w = re.sub('wl[‘’]', "wa\u0301l'", w)
        w = re.sub('yd[‘]', "ya\u0300d'", w)
        
        w = re.sub('(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)[‘’]', r"\1#\2'", w)
    ##############################################
    ### Incorrect use of ‘ instead of dagbasinna:
        w = re.sub('(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)‘(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)', r"\1\2", w)
        w = w.replace("\u07d1", "")
        w = w.replace('X', r"n")

    ### TONES (long):
        w = re.sub('(a|e|H|i|o|O|u)\u07ee\u07f2', "\\1\u0301\\1n`", w)
        w = re.sub('(a|e|H|i|o|O|u)\u07ee', "\\1\u0301\\1`", w)
        w = re.sub('(a|e|H|i|o|O|u|N)\u07ef', "\\1\u0301\\1", w)
        w = re.sub('(a|e|H|i|o|O|u|N)\u07f0', "\\1\u0300\\1", w)
        w = re.sub('(a|e|H|i|o|O|u|N)\u07f1', "\\1\u030c\\1", w)

    ### REMOVE flowting low tone from "i" and "n" pronouns:
        w = re.sub('\b([iN])\u0301`', "\\1\u0301", w)
        
    ### if N'Ko Text already contains LATIN NUMBERS (happened in Solomana Kante Kurukanfuwa) JJM nov 2024
        # REVERSE NUMBERS : 31 in N'Ko is 13 in latin !
        def reverse(m):
            digits=m.groups()[0]
            digitsr = digits[len(digits)::-1]
            return digitsr
        w = re.sub(r'([0-9][0-9]+)',reverse,w)
        # otherwise, the reversal comes with the replacement of RTL characters with LTR characters
        # for numbers just as well as for words

    ### NUMERALS:
        w = w.replace('\u07c0', r"0")
        w = w.replace('\u07c1', r"1")
        w = w.replace('\u07c2', r"2")
        w = w.replace('\u07c3', r"3")
        w = w.replace('\u07c4', r"4")
        w = w.replace('\u07c5', r"5")
        w = w.replace('\u07c6', r"6")
        w = w.replace('\u07c7', r"7")
        w = w.replace('\u07c8', r"8")
        w = w.replace('\u07c9', r"9")
        w = re.sub('r(\d)\u07f2', r"\1nan", w)
        w = re.sub('r(\d) \u07f2', r"\1nan", w) # I notice it is considered separate JJM 28/10/2024
        w = re.sub('r\u07f2(\d)', r"\1nan", w)  # is it not the reverse? JJM 28/10/2024B
        w = re.sub('r\u07f2 (\d)', r"\1nan", w)  # is it not the reverse? JJM 28/10/2024B
        #NB : none of these 4 approaches work ?


    ### NASALIZATION MARK:    
        w = w.replace('\u07f2', r"n")

    ##  s/[-,;:\.\x84\x85\"\x91-\x94\xAB\xBB\x96\x97\(\)\?\!]//g;

        w = w.replace('H', r"ɛ")
        w = w.replace('O', r"ɔ")
        w = w.replace('Y', r"ɲ")
        w = w.replace('R', r"rr")
        w = w.replace('G', r"gb")
        w = w.replace('S', r"sh")   # sh
        w = w.replace('D', "d\u0323")   ### D.  u0323=Combining dot below
        w = w.replace('Q', "\u0127")    ### H.  Latin Small Letter H With Stroke (U+0127)
        w = w.replace('J', "\u0292")    ### C. = zh - why not j ???
        w = w.replace('A', "\u0295")    ### A"  Latin Letter Pharyngeal Voiced Fricative (U+0295)
        w = w.replace('F', "\u03b8")    ### S"  Greek Small Letter Theta (U+03B8)
        w = w.replace('T', "t\u0323")   ### J"  u0323=Combining dot below
        w = w.replace('Z', "z\u0323")   ### J"  u0323=Combining dot below
        w = w.replace('C', "s\u0323")   ### S=  u0323=Combining dot below
        w = re.sub('[‘]', r"`", w)
        w = re.sub('[’]', r"'", w)
        w = w.replace('_', '')
        w = w.replace('\u0640', '')
        w = w.replace('N', 'n')
        w = re.sub('^i\u0301`$', 'i\u0301', w)

        if debug:
            print("LAT", w,)
        w = self.normalize_tones(w)
        
        if debug:
            print("TNL", w)
        return [w]

    def normalize_tones(self, word):
        """Replace surface tones resulting from the plain NKO>latin conversion with deep (lexical) tones"""
        word = word.replace('\u030c', '\u0300')
        if 'N\u0301' in word:
            Nlow = 0
        elif 'N\u0300' in word:
            Nlow = 1
        else:
            Nlow = 3

        pieces = word.split('N\u0301')
        outword = []
        for piece in pieces:
            piece = re.sub('(?P<t>[\u0300\u0301])', '\g<t>|', piece)
            piece = re.sub('(?P<v>[aeiouɛɔ])(?P<t>[\u0300\u0301])\|(?P=v)', '\g<v>\g<t>\g<v>|', piece)

            syllables = piece.split('|')
            if '\u0300' in syllables[0]:
                lowtone = 1
            else:
                lowtone = 0

            index = 0
            if lowtone == 1:
                for syl in syllables[1:]:
                    index += 1
                    syllables[index] = re.sub('[\u0300\u0301]', '', syl)
            else:
                for syl in syllables[1:]:
                    index += 1
                    if lowtone == 0 and '\u0301' in syl:
                        syllables[index] = syl.replace('\u0301', '')
                    elif lowtone == 0 and '\u0300' in syl:
                        lowtone = 2
                    elif lowtone == 2:
                        syllables[index] = re.sub('[\u0301\u0300]', '', syl)
            outword.append(''.join(syllables))

        if Nlow == 0:
            Njoiner = 'N\u0301'
        elif Nlow == 1:
            Njoiner = 'N\u0300'
        else:
            Njoiner = 'N'

        finalword = Njoiner.join(outword)
        finalword = re.sub('N\u0301ta\u0301(`?)', 'Ntan\1', finalword)
        return finalword

