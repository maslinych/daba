#! /usr/bin/env python
# coding=utf-8

import unicodedata
import sys
import Levenshtein

def differential_encode (form_non_tonal, form_tonal) :

	form_non_tonal = unicodedata.normalize('NFD', form_non_tonal)
	form_tonal = unicodedata.normalize('NFD', form_tonal)
	ops = Levenshtein.editops(form_non_tonal, form_tonal)

	ret = ""
	# dl = False
	for op in ops :

		mode, p_src, p_dst = op
		ret += mode[0] + str(p_src)

		if mode == 'delete' :
			ret += form_non_tonal[p_src]
			#	dl = True
		else :
			ret += form_tonal[p_dst]
	#if dl:
	#	print ret, form_non_tonal,form_tonal
	return ret

def main () :

	form_non_tonal = u"dɔnnin"
	form_tonal     = u"dɔ́nni"
	form_non_tonal = u'malidenwx'
	form_tonal = u'Màlidenw'

	print form_non_tonal
	print form_tonal
	print differential_encode (form_non_tonal, form_tonal)

if __name__ == "__main__" : main()
