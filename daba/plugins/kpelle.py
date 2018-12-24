#!/usr/bin/env python
# coding: utf-8

from daba.plugins import OrthographyConverter
import regex
import unicodedata
import unittest


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


class TestConverter(unittest.TestCase):
    def test_convert(self):
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


if __name__ == '__main__':
    unittest.main()
