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

def differential_encode (form_non_tonal, form_tonal) :

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
	isconsistant = strcmp_non_tonal(form_non_tonal.lower(), form_tonal.lower())

	# debug
	"""
	if not isconsistant :
		print form_non_tonal.lower(), form_tonal.lower()
	"""

	if isconsistant :
		form_tonal_normalized = unicodedata.normalize('NFC', form_tonal)
		for position, c in enumerate(form_tonal_normalized) :
			if unicodedata.decomposition(c) :
				c_decomposed = unicodedata.normalize('NFD', c)
				alpha, markers = c_decomposed[0], c_decomposed[1:]
				try : 
					isupper1 = form_non_tonal[position-1].isupper()
				except : 
					print position, len(form_non_tonal)
				isupper2 = c.isupper()
				if isupper1 != isupper2 :
					if isupper1 :
						alpha.upper()
					else :
						alpha.lower()
				for marker in markers :
					ret += u"{}{}{}".format(position, alpha, marker.encode('raw_unicode_escape'))
		return [ret,True]
	else :
		return [None,False]

def differential_decode(form_non_tonal, code_tone) :

	code_normalized = unicodedata.normalize('NFC', code_tone.decode('raw_unicode_escape'))
	form_normalized = unicodedata.normalize('NFC', form_non_tonal)
	cursor = int(0)
	ret = str("")
	for i, c in enumerate(code_normalized) :
		if not i % 2 :
			# position de la lettre accentuée
			position = int(c)
		else :
			# précautions
			c_non_tonal = form_normalized[position]
			c_tonal = c
			if position >= len(form_non_tonal) or not strcmp_non_tonal(c_non_tonal, c_tonal) :
				return None

			ret += form_non_tonal[cursor : position] + c
			cursor = position + 1

	# le reste de la chaîne de caractères
	ret += form_non_tonal[cursor :]
	return ret

def main () :

	# une paire d'exemple
	token = u"woroduguyan"
	form =  u"wòroduguyàn"

	# encodage = x - y = z
	# x : token sans accents en UTF-8
	# y : token accentués en UTF-8
	# z : code tonal
	[diff, validity] = differential_encode(token, form)
	if validity :
		print u"{} - {} = {}" . format(form, token, diff)
	else :
		print u"La différence entre {} et {} n'est pas exclusivement tonale !" . format(form, token)

	# decodage
	# x + z = y
	# x : token sans accents en UTF-8
        # y : token accentués en UTF-8
        # z : code tonal
	form =  u"wòroduguyàn"
	token = u"aocdefghaan"
	if diff :
		form_recovered = differential_decode(token, diff)
		sys.stdout.write(u"{} + {} = ". format(token, diff))
		if form_recovered :
			print form_recovered
		else :
			print "(le décodage est impossible !)"

if __name__ == "__main__" : main()
