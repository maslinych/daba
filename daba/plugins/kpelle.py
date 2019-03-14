#!/usr/bin/env python
# coding: utf-8

from daba.plugins import OrthographyConverter
import regex
import unicodedata
import unittest
import funcparserlib.lexer
import re


class KpelleMKOldToNew(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'kpellemkoldtonew'
        self.desc = 'Convertor from old MK orthography to new one'

    def convert_nasals(self, word):
        u"a̰a̰ -> aan, lòpɛ̰́ɛ̰̀ -> lòpɛ́ɛ̀n"
        return regex.sub(
            u'(.)\u0330([\u0300\u0301\u0302\u030C])?((.)\u0330([\u0300\u0301\u0302\u030C])?)?',
            u'\\1\\2\\4\\5n', word)

    def simplify_tones(self, word):
        u"Càà -> Càa, Cáá -> Cáa"
        return regex.sub(
            u'(.)(?P<tone>[\u0300\u0301\u0302\u030C])(.)(?P=tone)((ŋ)(?P=tone))?',
            u'\\1\\2\\3\\5', word)

    def contract_to_circumflex(self, word):
        u"Cáà -> Câa, Cáŋ̀ -> Câŋ, Cááŋ̀ -> Câaŋ"
        return regex.sub(u'(.)[\u0301]((.)[\u0301])?(.)[\u0300]',
                         u'\\1\u0302\\3\\4', word)

    def simplify_repeated_tones(self, word):
        u"ɓálá -> ɓála, lɛ̀ɓɛ̀lɛ́ɓɛ́ -> lɛ̀bɛlɛ́ɓɛ"
        reptones = regex.compile(
            u'(.)(?P<tone>[\u0300\u0301\u0302\u030C])([^\u0300\u0301\u0302\u030C-]+)(?P=tone)')
        while regex.search(reptones, word):
            word = regex.sub(reptones, u'\\1\\2\\3', word)
        return word

    def contract_to_hacek(self, word):
        u"gànǎ -> gǎna, hòŋ̌ -> hǒŋ, hɔ̀ɔ̀lǐ -> (hɔ̀ɔlǐ) -> hɔ̌ɔli"
        return regex.sub(
            u'(.)[\u0300]([^\u0300\u0301\u0302\u030C-]+)[\u030C]',
            u'\\1\u030C\\2', word)
            
    def convert(self, token):
        """
        Main conversion method
        Convert tone marking to a more compact form
        """
        word = unicodedata.normalize('NFKD', token)
        word = self.convert_nasals(word)
        word = self.contract_to_circumflex(word)
        word = self.simplify_tones(word)
        word = self.contract_to_hacek(word)
        word = self.simplify_repeated_tones(word)
        return word


class KpelleEvangelieToPract(OrthographyConverter):
    def __init__(self, *args, **kwargs):
        self.title = 'kpelleoldtopract'
        self.desc = 'Convertor from Kpelle old (Evangelie) orthography into new (practical)'
        self.conversion_table = {
            u'ngh': u'ngh',
            u'bh': u'ɓ',
            u'gh': u'ɠ',
            u'hv': u'hw',
            u'dy': u'j',
            u'ng': u'ŋ',
            u'nw': u'ŋw',
            u'ny': u'ɲ',
            u'ö': u'ɔ',
            u'ou': u'u',
            u'è': u'ɛ',
            u'a=': u'ā',
            u'=a': u'ā',
            u'e=': u'ē',
            u'=e': u'ē',
            u'i=': u'ī',
            u'=i': u'ī',
        }
                           
    def graphemes_old(self, word):
        # split word into maximal length graphemes (old orthography)
        specs = [
                ('NGH', (u'ngh', re.I | re.U)),
                ('XH', (u'[bg]h', re.I | re.U)),
                ('HV', (u'hv', re.I | re.U)),
                ('NG', (u'ng', re.I | re.U)),
                ('NX', (u'n[wy]', re.I | re.U)),
                ('OU', (u'ou', re.I | re.U)),
                ('VX', (u'[AEIOaeio][\u0300\u0301\u0302\u0308]', re.U)),
                ('V=', (u'(?<!=)[AEIaei]=', re.U)),
                ('=V', (u'=[AEIaei](?!=)', re.U)),
                ('ANY', (u'.', re.U)),
                ]
        tok = funcparserlib.lexer.make_tokenizer(specs)
        r = [x for x in tok(unicodedata.normalize('NFKD', word))]
        # print 'CW', word, ':', r
        return r

    def convertg(self, grapheme):
        # convert a single grapheme into a list of corresponding graphemes
        # in new orthography
        if unicodedata.category(grapheme[0]) == 'Lu':
            case = unicode.title
        else:
            case = unicode.lower
        grapheme = unicodedata.normalize('NFKD', grapheme)
        try:
            g = case(self.conversion_table[grapheme.lower()])
        except KeyError:
            g = grapheme
        return g

    def final_n(self, word):
        return word[:-1] + u'ŋ'

    def replace_e_accent(self, word):
        if word in [u'Jésus', u'Jérusalem']:
            return word
        return re.sub(u'e\u0301', 'e', word)

    def fix_ngh(self, word):
        for pattern in [u'galandyongha']:
            if re.match(pattern, word, re.U | re.I):
                word = word.replace(u'ngh', u'ŋɠ')
                break
        else:
            word = word.replace(u'ngh', u'nɠ')
        return word

    def convert_circumflex(self, word):
        """
        Convert vowels with circumflex
        """
        if re.match(u'[Pp]a\u0302que', word):
            return word
        word = regex.sub(u'(?<![nmŋɲ][^nmŋɲ]{0,3})([EeOoAa]\u0302)(?!ŋ$)', u'\\1n', word, flags=re.I)
        word = re.sub(u'e\u0301e\u0302', u'ɛɛ', word, flags=re.I)
        word = re.sub(u'e\u0301a\u0302', u'ɛa', word, flags=re.I)
        word = re.sub(u'e\u0302', u'ɛ', word, flags=re.I)
        word = re.sub(u'o\u0302', u'ɔ', word, flags=re.I)
        word = re.sub(u'(a)\u0302', u'\\1', word, flags=re.I)
        return word

    def convert(self, token):
        """
        Main conversion method
        """
        graphemes = ''.join([self.convertg(g.value) for g in self.graphemes_old(token)])
        if u'ngh' in graphemes:
            graphemes = self.fix_ngh(graphemes)
        if graphemes.endswith('n'):
            graphemes = self.final_n(graphemes)
        if u'\u0302' in graphemes:
            graphemes = self.convert_circumflex(graphemes)
        if u'e\u0301' in graphemes:
            graphemes = self.replace_e_accent(graphemes)
        return [graphemes]


class TestConverter(unittest.TestCase):
    def test_convert_old(self):
        conv = KpelleEvangelieToPract()
        self.assertEqual(conv.convert(u'kpôn'), [u'kpɔŋ'])
        self.assertEqual(conv.convert(u'bê'), [u'bɛn'])
        self.assertEqual(conv.convert(u'tamâ'), [u'tama'])
        self.assertEqual(conv.convert(u'nouâ'), [u'nua'])
        self.assertEqual(conv.convert(u'‘nyây'), [u'‘ɲay'])
        self.assertEqual(conv.convert(u'mêy'), [u'mɛy'])
        self.assertEqual(conv.convert(u'nyènê'), [u'ɲɛnɛ'])
        self.assertEqual(conv.convert(u'nyongô'), [u'ɲoŋɔ'])
        self.assertEqual(conv.convert(u'kölö'), [u'kɔlɔ'])
        self.assertEqual(conv.convert(u'lélé'), [u'lele'])
        self.assertEqual(conv.convert(u'Pharisiengha'), [u'Pharisienɠa'])
        self.assertEqual(conv.convert(u'Romaingha'), [u'Romainɠa'])
        self.assertEqual(conv.convert(u'galandyongha'), [u'galandyoŋɠa'])
        #self.assertEqual(conv.convert(u''), [u''])
        #self.assertEqual(conv.convert(u''), [u''])
         
        
    def test_convert_mk(self):
        conv = KpelleMKOldToNew()
        self.assertEqual(conv.convert(u'yɔ̀wâ'), u'yɔ̀wâ')
        self.assertEqual(conv.convert(u'kèɓéŋ̀'), u'kèɓêŋ')
        self.assertEqual(conv.convert(u'kwɛ́lɛ́ɛ́ŋ́'), u'kwɛ́lɛɛŋ')
        self.assertEqual(conv.convert(u'làláŋ̀'), u'làlâŋ')
        self.assertEqual(conv.convert(u'kpɛ̀áŋ̀'), u'kpɛ̀âŋ')
        self.assertEqual(conv.convert(u'kpɛ̀lɛ̀ɠɛ́lɛ́ŋ̀'), u'kpɛ̀lɛɠɛ́lɛ̂ŋ')
        self.assertEqual(conv.convert(u'Kpɛ́líwólô'), u'Kpɛ́liwolô')
        self.assertEqual(conv.convert(u'làɓálî'), u'làɓálî')
        self.assertEqual(conv.convert(u'láámààmúŋ̀'), u'láamàamûŋ')
        self.assertEqual(conv.convert(u'hwɔ̀áhwɔ̀áŋ̀'), u'hwɔ̀áhwɔ̀âŋ')
        self.assertEqual(conv.convert(u'kùnúkùnǔ'), u'kùnúkǔnu')
        self.assertEqual(conv.convert(u'kùnúŋ́-gbàɠà'), u'kùnúŋ-gbàɠa')
        self.assertEqual(conv.convert(u'hɛ̰́hɛ̰́'), u'hɛ́nhɛn')
        self.assertEqual(conv.convert(u'hwḭ́ɛ̰́'), u'hwíɛn')
        self.assertEqual(conv.convert(u'lòpɛ̰́ɛ̰̀'), u'lòpɛ̂ɛn')
        self.assertEqual(conv.convert(u'lɛ̀ɓɛ̀lɛ́ɓɛ́'), u'lɛ̀ɓɛlɛ́ɓɛ')
        self.assertEqual(conv.convert(u'bɛ̀à-kwɛ̀lì'), u'bɛ̀a-kwɛ̀li')
        self.assertEqual(conv.convert(u'ɓíílóŋ́-gààlè'), u'ɓíiloŋ-gàale')
        self.assertEqual(conv.convert(u'búlú-búlú'), u'búlu-búlu')

if __name__ == '__main__':
    unittest.main()
