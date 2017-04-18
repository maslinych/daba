#! /usr/bin/env python
# coding=utf-8

import unicodedata
import sys
import Levenshtein

# todo :
# il faut remplacer le module actuel par ceci
# https://pypi.python.org/pypi/weighted-levenshtein/0.1
# pour permettre de pénaliser les autres opérations que
# l'insetion qui est massivement utilisée par
# la modélisation des tons et des pauses en prenant compte
# également des replacements dans certains d'alphabet
# par exemple, e par epsilon

markers_tone =  [unichr(0x0300),unichr(0x0301),unichr(0x0302),unichr(0x030c)]
markers_pause = [unichr(0x002e)]
PREDICTION_GENERAL = True
PREDICTION_TONES_PAUSE = True

def differential_encode (form_non_tonal, form_tonal) :

	form_non_tonal = unicodedata.normalize('NFD', form_non_tonal)
	form_tonal = unicodedata.normalize('NFD', form_tonal)
	ops = Levenshtein.editops(form_non_tonal, form_tonal)

	ret = ""
	if PREDICTION_TONES_PAUSE :
		markers = markers_tone + markers_pause
	else : # PREDITION_TONES_ONLY
		markers = markers_tone
	for op in ops :

		mode, p_src, p_dst = op
		# codage des marqueurs de ton
		if mode == "delete" :
			if form_non_tonal[p_src] in markers or PREDICTION_GENERAL :
				ret += 'd' + str(p_src) + form_non_tonal[p_src]
		else : # mode == "insert" or "replace"
			if form_tonal[p_dst] in markers or PREDICTION_GENERAL :
				if mode == "replace" : ret += 'r'
				ret += str(p_src) + form_tonal[p_dst]
	return ret

def main () :

	form_non_tonal = u'abécèi'
	form_tonal     = u'àbècel'

	print form_non_tonal
	print form_tonal
	print differential_encode (form_non_tonal, form_tonal)

if __name__ == "__main__" : main()
