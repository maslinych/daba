#! /usr/bin/env python
# coding=utf-8

import unicodedata,argparse,codecs,sys,re

class fileReader () :

	def __init__(self, customed_markers = "") :
		self.strp = \
			self.__get_cat_startwith('Zl') + \
			self.__get_cat_startwith('Zp') + \
			self.__get_cat_startwith('Zs') + '\n'
	        sep_sent  = \
			self.__get_cat_startwith('Pi') + \
			self.__get_cat_startwith('Pf') + \
			self.__get_cat_startwith('Po')
        	sep_token = \
			self.__get_cat_startwith('Zs')

		pat1   = u'([{}]+)'.format(sep_sent)
		pat2   = u'[{}]+'.format(sep_token)
		self.regex1 = re.compile(pat1, flags = re.IGNORECASE)
		self.regex2 = re.compile(pat2, flags = re.IGNORECASE)

		if not customed_markers :
			self.markers = self.__get_cat_startwith('Mn')
		else :
			self.markers = customed_markers

	def read(self, filein) :
        	sentences = list()
		with codecs.open(filein, 'r', 'utf-8') as file:
			for line in file :
				para = line.strip(self.strp)
				sents = self.regex1.split(para)
				for sent in sents :
					tokens = self.regex2.split(sent)
					sentence = list()
					for token in tokens :
						if token :
							sentence.append([self.__mask(token), self.__unicode_decomp(token)])
					if sentence :
						sentences.append(sentence)
		return sentences

	def __unicode_decomp(self, str_in) :
		return unicodedata.normalize('NFD', str_in)

	def __mask(self, str_in) :
		str_in = self.__unicode_decomp(str_in)
		return u"".join([c for c in str_in if c not in self.markers])

	def __get_cat_startwith(self, str_in) :
		return u"".join([unichr(i) for i in xrange(sys.maxunicode) \
			if unicodedata.category(unichr(i)).startswith(str_in)])

def view_allsents(sentences) :
	s_num = 0
	for sent in sentences :
		if sent :
			t_num = 0
			for token in sent :
				if token :
					print u"{:6d}{:3d}: '{}' -> '{}'".format(s_num,t_num,token[0],token[1])
					t_num += 1
			s_num += 1
			print

if __name__ == "__main__" :

	# interface en ligne de commande
	parser = argparse.ArgumentParser()
	parser.add_argument('file')
	args = parser.parse_args()

	fr = fileReader()
	sentences = fr.read(args.file)
	view_allsents(sentences)
