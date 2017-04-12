#! /usr/bin/env python
# coding=utf-8

import string
import unicodedata
import sys

tbl_punc = dict.fromkeys(i for i in xrange(sys.maxunicode) if unicodedata.category(unichr(i)).startswith('P'))

def strip_punctuations(form) :
	return form.translate(tbl_punc)

def strip_tones(form_tonal) :

	"""
	référence :
		http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
    note :
		'Mn' pour Nonspacing_Mark
	"""
        form_tonal     = unicodedata.normalize('NFD', form_tonal)
        form_tonal     = "".join(c for c in form_tonal \
		if (unicodedata.category(c) != 'Mn') and (not unicodedata.category(c).startswith('P')))
	return form_tonal

def is_encodable(form_non_tonal, form_tonal, encodable_sets = []) :

	form_non_tonal = strip_tones(form_non_tonal).lower()
	form_tonal     = strip_tones(form_tonal).lower()

	if not encodable_sets :
		return form_non_tonal == form_tonal
	else :
		if len(form_non_tonal) != len(form_tonal) :
			return False

	        for c1, c2 in zip(form_non_tonal.lower(), form_tonal.lower()) :
        	        if c1 != c2 :
                	        is_equivalent = False
                        	for lst in encodable_sets :
                                	if c1 in lst and c2 in lst :
	                                        is_equivalent = True
        	                                break
                	        if not is_equivalent :
					# print c1,c2
                        	        return False
	        return True

def differential_encode (form_non_tonal, form_tonal, encodable_sets = []) :

	"""
    description :
		Cette fonction encode les informations tonales à partir de la forme non-tonal et
			la forme tonal d'un même mot qu'elle reçoit en argument.
		Le codage différential des informations s'exprime sous la forme illustrée dans l'exemple ci-dessous

		exemple :
			soit form_non_tonal = u"wòroduguyàn", form_tonal = u"woroduguyan"
				leur différence sera représenté par le code 1ò9à ou 1o\u03009a\u0300 qui s'est composé
				des suites dont chacune s'ecrit en trois caractère dont respectivement
				le prémier marque la position de le marqueur du ton,
				le deuxième note l'alphabet non-accentué sur lequel le premier s'ajoute dans le mot
				le dernier représente le marqueur par son code définie dans le standard UTF-8 comme
					'Combining Diacritical Marks'
			note : ò est la concaténation de deux caractères, ils s'affichent
				comme un caractère entière en raison du traitement du système 
				d'exploitation sur l'affichage des chaînes de caractère en unicode
       """

	ret = ""
	if is_encodable(form_non_tonal, form_tonal, encodable_sets) :

		form_tonal     = unicodedata.normalize('NFC', form_tonal)
		form_tonal     = strip_punctuations(form_tonal)
		form_non_tonal = strip_punctuations(form_non_tonal)

		cursor = 0
		for c1, c2 in zip(form_tonal, form_non_tonal) :
			if c1 != c2:
				if unicodedata.decomposition(c1):
					c3   = unicodedata.normalize('NFD', c1)
					alpha, markers = c3[0], c3[1:]
					isupper_token  = c2.isupper()

					# conversion de caisse des lettres
					if isupper_token != c1.isupper() :
						if isupper_token : alpha.upper()
						else             : alpha.lower()

					# codage 2 chiffres pour la position, 1 lettre pour le caractère remplaçant
					ret += u"{:02d}".format(cursor) + c3
				else :
					ret += u"{:02d}".format(cursor) + c1
			cursor += 1
		return [ret,True]
	else :
		return [None,False]

def differential_decode(form_non_tonal, code_tone, encodable_set = []) :

	code_normalized = unicodedata.normalize('NFC', code_tone)
	form_normalized = unicodedata.normalize('NFC', form_non_tonal)
	cursor = int(0)
	ret = str("")

	str_buffer = ""
	for i, c in enumerate(code_normalized) :
		if i % 3 != 2 :
			# position de la lettre accentuée
			str_buffer += c
		else :
			# précautions
			position = int(str_buffer)

			c_non_tonal = form_normalized[position]
			c_tonal = c
			if position >= len(form_non_tonal) or not is_encodable(c_non_tonal, c_tonal, encodable_set) :
				return None

			ret += form_non_tonal[cursor : position] + c
			cursor = position + 1
			str_buffer = ""


	# le reste de la chaîne de caractères
	ret += form_non_tonal[cursor :]
	return ret

def main () :

	# une paire d'exemple
	token = u"woroduguyanfdsfjle"
	form =  u"wòroduguy¤nfdsfjlë"
	encodable_set = [{u"¤",u"a"}]

	# encodage = x - y = z
	# x : token sans accents en UTF-8
	# y : token accentués en UTF-8
	# z : code tonal
	[diff, validity] = differential_encode(token, form, encodable_set)
	if validity :
		print u"{} - {} = {}" . format(form, token, diff)
	else :
		print u"La différence entre {} et {} n'est pas exclusivement tonale !" . format(form, token)

	# decodage
	# x + z = y
	# x : token sans accents en UTF-8
        # y : token accentués en UTF-8
        # z : code tonal
	if diff :
		form_recovered = differential_decode(token, diff, encodable_set)
		sys.stdout.write(u"{} + {} = ". format(token, diff))
		if form_recovered :
			print form_recovered
		else :
			print "(le décodage est impossible !)"

if __name__ == "__main__" : main()
