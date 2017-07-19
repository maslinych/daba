#! /usr/bin/env python
# coding=utf-8

import unicodedata,argparse,codecs,sys,re

def get_cat_startwith(str_in) :

	return u"".join([unichr(i) for i in xrange(sys.maxunicode) if unicodedata.category(unichr(i)).startswith(str_in)])

def file_to_sentences(filein) :

	# regex for spliting / tokenization
	strp = get_cat_startwith('Zl') + \
	       get_cat_startwith('Zp') + \
     	       get_cat_startwith('Zs')
	sep_token  = get_cat_startwith('Zs')
	sep_sent = get_cat_startwith('Pi') + \
	           get_cat_startwith('Pf') + get_cat_startwith('Po')
	pat1 = u'([{}]+)'.format(sep_sent)
	pat2 = u'[{}]+'.format(sep_token)
	regex1 = re.compile(pat1, flags=re.IGNORECASE)
	regex2 = re.compile(pat2, flags=re.IGNORECASE)

	# routine de lecture
	sentences = list()
	try :
		with codecs.open(filein, 'r', 'utf-8') as file:
			for line in file :
				para = line.strip(strp)
				sents = regex1.split(para)
				for sent in sents :
					tokens = regex2.split(sent)
					sentence = list()
					for token in tokens :
						if token :
							# [prediction source, prediction destination]
							sentence.append([mask(token), token])
					if sentence :
						sentences.append(sentence)
		return sentences
	except :
		return []

def mask(str_in, sym_to_mask = get_cat_startwith('Mn')) :
	return u"".join([c for c in str_in if c not in sym_to_mask])

if __name__ == "__main__" :

	# interface en ligne de commande
	#parser = argparse.ArgumentParser()
	#parser.add_argument('file')
	#args = parser.parse_args()
	file = "../Tashkeela-arabic-diacritized-text-utf8-0.3/texts.txt/تحفة المحتاج في شرح المنهاج.txt"
	file = "../Tashkeela-arabic-diacritized-text-utf8-0.3/texts.txt/فضائل مجالس الذكر .txt"

	#
	sentences = file_to_sentences(file)
	s_num = 0
	for sent in sentences :
		if sent :
			t_num = 0
			for token in sent :
				if token[1] :
					print u"{:6d}{:3d}: {} -> {}".format(s_num,t_num,token[0],token[1])
					t_num += 1
			s_num += 1
