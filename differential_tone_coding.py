#! /usr/bin/env python
# coding=utf-8

import string
import unicodedata
import sys

tbl_punc = dict.fromkeys(i for i in xrange(sys.maxunicode) if unicodedata.category(unichr(i)).startswith('P'))
def strip_punctuations(form) :

	try :
		return form.translate(tbl_punc)
	except TypeError:
		return form

def strip_tones(form_tonal) :

	"""
	Reference :
	http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
	"""
        form_tonal     = unicodedata.normalize('NFD', form_tonal)
        form_tonal     = "".join(c for c in form_tonal \
		if (unicodedata.category(c) != 'Mn') and (not unicodedata.category(c).startswith('P')))
	return form_tonal

def is_encodable(form_non_tonal, form_tonal, encodable_sets = []) :

	# ignorer les ponctuations
	form_non_tonal = strip_punctuations(form_non_tonal)
	form_tonal     = strip_punctuations(form_tonal)
	# suppression des accents
	form_non_tonal = strip_tones(form_non_tonal).lower()
	form_tonal     = strip_tones(form_tonal).lower()
	# comparaison
	if not encodable_sets :
		return form_non_tonal == form_tonal
	else :
		# comparaison des longueurs
		if len(form_non_tonal) != len(form_tonal) :
			return False
		# comparaison des caractères
	        for c1, c2 in zip(form_non_tonal, form_tonal) :
        	        if c1 != c2 :
                	        caracters_encodable = False
                        	for lst in encodable_sets :
                                	if c1 in lst and \
					   c2 in lst     :
	                               		caracters_encodable = True
        	                                break
                	        if not caracters_encodable :
					return False
	        return True

def differential_encode (form_non_tonal, form_tonal, encodable_sets = []) :


	ret = ""
	if is_encodable(form_non_tonal, form_tonal, encodable_sets) :

		form_tonal     = strip_punctuations(unicodedata.normalize('NFD', form_tonal))
		form_non_tonal = strip_punctuations(strip_tones(form_non_tonal))

		cursor = 0
		markers = ""
		alpha = ""
		ret = ""
		for c in form_tonal :
			if unicodedata.category(c) == "Mn" :
				markers += c
			else :
				if markers :
					ret += u"{:02d}".format(cursor - 1) + alpha + markers
				if c.isupper() != form_non_tonal[cursor].isupper() :
					if c.isupper() : alpha = c.lower()
					else           : alpha = c.upper()
				else :
					alpha = c
				markers = ""
				cursor += 1
		if markers :
			ret += u"{:02d}".format(cursor - 1) + alpha + markers

		validity = True
	else :
		validity = False

	return [ret, validity]

def differential_decode(form_non_tonal, code_tone, encodable_set = []) :

	if not code_tone : return form_non_tonal

	code_tone = unicodedata.normalize('NFD', code_tone)
	form_non_tonal = unicodedata.normalize('NFC', form_non_tonal)
	ret = ""

	alpha_buffer = ""
	number_buffer = ""
	markers_buffer = ""
	cursor = 0
	for c in code_tone :
		if unicodedata.category(c) == "Nd" :
			if number_buffer and alpha_buffer and markers_buffer :
				ret += form_non_tonal[cursor : int(number_buffer)]
				ret += alpha_buffer + markers_buffer
				cursor = int(number_buffer) + 1
				alpha_buffer = ""
				markers_buffer = ""
				number_buffer = ""

			number_buffer += c
		elif unicodedata.category(c) == "Mn" :
			markers_buffer += c
		else :
			alpha_buffer += c

	if number_buffer and alpha_buffer and markers_buffer :
		ret += form_non_tonal[cursor : int(number_buffer)]
		ret += alpha_buffer + markers_buffer

	return ret

def main () :

	# une paire d'exemple
	token = u"worODuguyaofdãfileɔ"
	form =  u"wòrɔ̀;dUg,,u;y¤õfdafĩleɔ̃̂"
	encodable_set = [{u"¤",u"a"}, {u"ɔ",u"o"}]

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
