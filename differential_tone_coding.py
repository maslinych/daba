#! /usr/bin/env python
# coding=utf-8

import unicodedata
import sys

def strcmp_non_tonal (ustr1, ustr2) :

	"""
	descritpion :
		Cette fonction vérifie si la différence des
	deux chaînes de caractères qu'elle reçoit ne porent que sur leurs marqueurs de ton

	args : ustr1 (str), ustr2 (str)
	returns : (boolean)

	référence :
		http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
	note :
		'Mn' pour Nonspacing_Mark
	"""

	def strip_tone (str) :
		return ''.join(c for c in unicodedata.normalize('NFD', str)
			if unicodedata.category(c) != 'Mn')

	return strip_tone(ustr1) == strip_tone(ustr2)

def differential_coding_for_tone (form_non_tonal, form_tonal) :

	"""
	description :
		Cette fonction encode les informations tonales à partir de la forme non-tonal et 
	la forme tonal d'un même mot qu'elle reçoit en argument.
		Le codage différential des informations s'exprime sous la forme illustrée dans
	l'exemple ci-dessous

	exemple :
		soit form_non_tonal = u"wòroduguyàn", form_tonal = u"woroduguyan"
		leur différence sera représenté par le code 1ò9à ou 1o\u03009a\u0300 qui s'est composé
		des suites dont chacune s'ecrit en trois caractère dont respectivement
			le prémier marque la position de le marqueur du ton,
			le deuxième note l'alphabet non-accentué sur lequel le premier s'ajoute dans le mot
			le dernier représente le marqueur par son code définie dans le standard UTF-8 comme
			'Combining Diacritical Marks'
		note : ò est la concaténation de deux caractères, ils s'affichent comme un caractère entière en raison du traitement
		du système d'exploitation sur l'affichage des chaînes de caractère en unicode
	"""

	ret = ""
	if strcmp_non_tonal(form_non_tonal, form_tonal) :
		form_tonal_normalized = unicodedata.normalize('NFC', form_tonal)
		for position, c in enumerate(form_tonal_normalized) :
			if unicodedata.decomposition(c) :
				c_decomposed = unicodedata.normalize('NFD', c)
				alpha, markers = c_decomposed[0], c_decomposed[1:]
				for marker in markers :
					ret += u"{}{}{}".format(position, alpha, marker.encode('raw_unicode_escape'))
		return ret
	else :
		return None

def main () :

	token = u"woroduguyan"
	form = u"wòroduguyàn"
	diff = differential_coding_for_tone(token, form)
	if diff :
		print u"{} - {} = {}" . format(form, token, diff)
	else :
		print "La différence entre {} et {} n'est pas exclusivement tonale !" . format(form, token)

if __name__ == "__main__" : main()
