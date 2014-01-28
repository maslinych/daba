#!/usr/bin/python
# -*- coding: utf8 -*-

from . import OrthographyConverter
import re


class NkoToLatin(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'nko'
        self.desc = 'Convertor from NKO to latin script'

    def convert(self, token):
        """
        Main conversion method
        """
        
        w = token
    ### FOREIGN sounds with diacritics:
        w = re.sub(u'\u07d6\u07ed', ur"z", w)
        w = re.sub(u'\u07db\u07ed', ur"S", w)   ### SH
        w = re.sub(u'\u07dc\u07ed', ur"g", w)
        w = re.sub(u'\u07dd\u07ed', ur"v", w)
        w = re.sub(u'\u07d8\u07ed', ur"D", w)   ### D.
        w = re.sub(u'\u07e4\u07ed', ur"Q", w)   ### H.
        w = re.sub(u'\u07d7\u07ed', ur"J", w)   ### C.
        w = re.sub(u'\u07de\u07ed', ur"x", w)   ### K.
        w = re.sub(u'\u07d5\u07ed', ur"T", w)   ### T.
        
        w = re.sub(u'\u07ca\u07f3', ur"A", w)   ### A"
        w = re.sub(u'\u07db\u07f3', ur"F", w)   ### S"
        w = re.sub(u'\u07d6\u07f3', ur"Z", w)   ### J"
        
        w = re.sub(u'\u07db\u07eb', ur"C", w)   ### S=
        w = re.sub(u'\u07de\u07eb', ur"q", w)   ### K=

        w = re.sub(u'\u07f3', ur"\u0308", w)
        w = re.sub(u'\u07f6', ur"o-DENNEN", w)
        w = re.sub(u'\u07cb\u0623', ur" { ", w)
        w = re.sub(u'\u07cb\u0625', ur" } ", w)	

    ### VOWELS:
        w = re.sub(u'\u07ca', ur"a", w)
        w = re.sub(u'\u07cb', ur"e", w)
        w = re.sub(u'\u07cc', ur"i", w)
        w = re.sub(u'\u07cd', ur"H", w)
        w = re.sub(u'\u07ce', ur"u", w)
        w = re.sub(u'\u07cf', ur"o", w)
        w = re.sub(u'\u07d0', ur"O", w)
    ### SYLLABIC N
        w = re.sub(u'\u07d2', ur"N", w)

    ### CONSONANTS:
        w = re.sub(u'\u07d3', ur"b", w)
        w = re.sub(u'\u07d4', ur"p", w)
        w = re.sub(u'\u07d5', ur"t", w)
        w = re.sub(u'\u07d6', ur"j", w)
        w = re.sub(u'\u07d7', ur"c", w)
        w = re.sub(u'\u07d8', ur"d", w)
        w = re.sub(u'\u07d9', ur"r", w)
        w = re.sub(u'\u07da', ur"R", w)
        w = re.sub(u'\u07db', ur"s", w)
        w = re.sub(u'\u07dc', ur"G", w)
        w = re.sub(u'\u07dd', ur"f", w)
        w = re.sub(u'\u07de', ur"k", w)
        w = re.sub(u'\u07df', ur"l", w)
        w = re.sub(u'\u07e0', ur"n", w)   # Na woloso
        w = re.sub(u'\u07e1', ur"m", w)
        w = re.sub(u'\u07e2', ur"Y", w)   # Nya
        w = re.sub(u'\u07e3', ur"n", w)
        w = re.sub(u'\u07e4', ur"h", w)
        w = re.sub(u'\u07e5', ur"w", w)
        w = re.sub(u'\u07e6', ur"y", w)
        w = re.sub(u'\u07e7', ur"y", w)   # Nya woloso

    ### APOSTROPHES:
        w = re.sub(u'\u07f4', ur"’", w)
        w = re.sub(u'\u07f5', ur"‘", w)



    ### PUNCTUATION:
        w = re.sub(u'\u060c', ur",", w)  # Arabic comma
        w = re.sub(u'\u061f', ur"?", w)  # Arabic question mark
        w = re.sub(u'؛', ur" ;", w)
    #    w = re.sub(u'\u07f8', ur" NKO_COMMA ", w)
    #    w = re.sub(u'\u07f9\u07f9\u07f9', ur" NKO_EXCLM3 ", w)
    #	w = re.sub(u'\u07f9\u07f9', ur" NKO_EXCLM2 ", w)
    #	w = re.sub(u'\u07f9', ur" NKO_EXCLM ", w)
        w = re.sub(u'\u07fa', ur"-", w)
#        w = re.sub(u'\x96', ur"-", w)
#        w = re.sub(u'\x97', ur"--", w)
    #    w = re.sub(u'\.\.\.', ur" \x85", w)
    #    w = re.sub(u'\.\.', ur" \.", w)
        w = re.sub(u'\.', ur" . ", w)
        w = re.sub(u':', ur" :", w)
        w = re.sub(u'\(', ur" (", w)
        w = re.sub(u'\)', ur" )", w)

        w = re.sub(u'\u066a', ur"%", w)	
        w = re.sub(u'\t', ur" ", w)
        w = re.sub(u'\s+', ur" ", w)


    ### MARKING HIGH TONE:
        w = re.sub(u'(a|e|H|i|o|O|u|N)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q|-)', ur"\1\u0301\2", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)(a|e|H|i|o|O|u|N)', ur"\1\u0301\2", w)
        w = re.sub(u'(a|e|H|i|o|O|u)$', ur"\1\u0301`", w, flags=re.U)
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
        w = re.sub(u'a\u0301lm[‘’]', ur"a\u0301la\u0301m'", w)
        w = re.sub(u'bd[‘’]', ur"ba\u0301d'", w)
        w = re.sub(u'br[‘]', ur"ba\u0301r'", w)
        w = re.sub(u'dO\u0301tl[’]', ur"dO\u0301ta\u0301l'", w)
        w = re.sub(u'fd[’]', ur"f\#d'", w)
        w = re.sub(u'fn[’]', ur"fa\u0301n'", w)
        w = re.sub(u'fr[‘’]', ur"fa\u0301r'", w)
        w = re.sub(u'Gr[‘’]', ur"Ga\u0300r'", w)
        w = re.sub(u'hákílímy[’]', ur"hákílímáy'", w)
        w = re.sub(u'hl[’]', ur"ha\u0301l'", w)
        w = re.sub(u'jk[‘]', ur"ja\u0301k'", w)
        w = re.sub(u'kf[’]', ur"ka\u0301f'", w)
        w = re.sub(u'kn[‘’]', ur"ka\u0301n'", w)
        w = re.sub(u'kY[‘]', ur"kE\u0301Y'", w)
        w = re.sub(u'látd[‘]', ur"látE\u0300d'", w)
        w = re.sub(u'dm[’]', ur"dE\u0300m'", w)
        w = re.sub(u'mákb[’]', ur"mákáb'", w)
        w = re.sub(u'mákl[’]', ur"mákíl'", w)
        w = re.sub(u'nr[’]', ur"na\u0301r'", w)
        w = re.sub(u'Yáml[’]', ur"Yámál'", w)
        w = re.sub(u'sr[‘]', ur"sa\u0300r'", w)
        w = re.sub(u'tl[’]', ur"ta\u0301l'", w)
        w = re.sub(u'td[‘’]', ur"tE\u0300d'", w)
        w = re.sub(u'wl[‘’]', ur"wa\u0301l'", w)
        w = re.sub(u'yd[‘]', ur"ya\u0300d'", w)
        
        w = re.sub(u'(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)[‘’]', ur"\1\#\2'", w)
    ##############################################
    ### Incorrect use of ‘ instead of dagbasinna:
        w = re.sub(u'(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)‘(b|p|t|j|c|d|r|R|s|G|f|k|l|n|m|Y|h|w|y|z|g|S|v|F|D|Q|J|A|T|Z|C|x|q)', ur"\1\2", w)
        
        w = re.sub("\u07d1", "", w)

        w = re.sub(u'X', ur"n", w)

    ### TONES (long):
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ee\u07f2', ur"\1\u0301\1n`", w)
        w = re.sub(u'(a|e|H|i|o|O|u)\u07ee', ur"\1\u0301\1`", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07ef', ur"\1\u0301\1", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07f0', ur"\1\u0300\1", w)
        w = re.sub(u'(a|e|H|i|o|O|u|N)\u07f1', ur"\1\u030c\1", w)

    ### REMOVE flowting low tone from "i" and "n" pronouns:
        w = re.sub(u'\b([iN])\u0301`', ur"\1\u0301", w)	
        
    ### NUMERALS:
        w = re.sub(u'\u07c0', ur"0", w)
        w = re.sub(u'\u07c1', ur"1", w)
        w = re.sub(u'\u07c2', ur"2", w)
        w = re.sub(u'\u07c3', ur"3", w)
        w = re.sub(u'\u07c4', ur"4", w)
        w = re.sub(u'\u07c5', ur"5", w)
        w = re.sub(u'\u07c6', ur"6", w)
        w = re.sub(u'\u07c7', ur"7", w)
        w = re.sub(u'\u07c8', ur"8", w)
        w = re.sub(u'\u07c9', ur"9", w)
        w = re.sub(u'(\d)\u07f2', ur"\1nan", w)

    ### NASALIZATION MARK:    
        w = re.sub(u'\u07f2', ur"n", w)

    ##  s/[-,;:\.\x84\x85\"\x91-\x94\xAB\xBB\x96\x97\(\)\?\!]//g;

    ### PUNCTUATION:
        w = re.sub(u' ,', ur", ", w)
        w = re.sub(u' !', ur"! ", w)
        w = re.sub(u' \?', ur"? ", w)
        w = re.sub(u' \.', ur"\.", w)
#        w = re.sub(u' \x85', ur"\x85 ", w)
        w = re.sub(u' :', ur": ", w)
        w = re.sub(u' ;', ur"; ", w)
        w = re.sub(u' \(', ur"(", w)
        w = re.sub(u' \)', ur")", w)

        w = re.sub(u'H', ur"ɛ", w)
        w = re.sub(u'O', ur"ɔ", w)
        w = re.sub(u'Y', ur"ɲ", w)
    #    w = re.sub(u'N', ur"n", w)
        w = re.sub(u'R', ur"rr", w)
        w = re.sub(u'G', ur"gb", w)
        w = re.sub(u'S', ur"sh", w)   # sh
        w = re.sub(u'D', ur"d\u0323", w)   ### D.
        w = re.sub(u'Q', ur"\u0127", w)    ### H.
        w = re.sub(u'J', ur"\u0292", w)    ### C. = zh
        w = re.sub(u'A', ur"\u0295", w)    ### A"
        w = re.sub(u'F', ur"\u03b8", w)    ### S"
        w = re.sub(u'T', ur"t\u0323", w)   ### J"
        w = re.sub(u'Z', ur"z\u0323", w)   ### J"
        w = re.sub(u'C', ur"s\u0323", w)   ### S=
        
        w = re.sub(u'd\u0323IErrEshIsh', ur"DIERESIS", w)
        w = re.sub(u'd\u0323en\u0301nEn', ur"DENNEN", w)
        
        w = re.sub(u'\u07f8', ur" , ", w)
        w = re.sub(u'\u07f9', ur" ! ", w)
        w = re.sub(u'[‘’]([^‘’])', ur"'\1", w)
        w = re.sub('_', '', w)
        
        return [w]
