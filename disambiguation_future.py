#!/usr/bin/python
# -*- coding: utf-8 -*-

# Auteur : Elvis Mboning, Stagiaire 2016, INALCO
# Auteur : Damien Nouvel, MCF, INALCO

# Le principale rôle de ce script est de créer des modèles de données pour l'apprentissage automatique avec CRFTagger.
# Le CRF implémenté provient du module tag de NLTK inspiré de CRFSuite (http://www.nltk.org/api/nltk.tag.html#module-nltk.tag.crf).
# Trois modèles sont possibles : les POS, les tons, les gloses

# Change 1: Use sentence boundaries as described in the input HTML file to construct input and evaluation input data.
# Change 2: Insertion of a tone encoder in order to improve the learning of tone prediction.
# Change 3 (i progress) : Implementation of the -d option (used with -i, -o) which serves to disambiguate
#           the parts of speech, tones, translation glosses of a parsed fihcer
#           where ambiguity remains by applying the learned CRF model to the data of reference.

import sys, re, codecs, random, glob,  time, random, os
import argparse
import formats,  grammar
from ntgloss import Gloss
from nltk.tag.crf import CRFTagger
from gdisamb import FileParser
from differential_tone_coding import differential_encode

import codecs, sys
sys.stdin = codecs.getreader('utf8')(sys.stdin)
sys.stdout = codecs.getwriter('utf8')(sys.stdout)
#lists_of_equivalence = [{u'e',u'ɛ',u'a'}, {u'o',u'ɔ'}]
lists_of_equivalence = []

def main():

	aparser = argparse.ArgumentParser(description='Daba disambiguator')
	aparser.add_argument('-v', '--verbose', help='Verbose output', default=False, action='store_true')
	aparser.add_argument('-l', '--learn', help='Learn model from data (and save as F if provided)', default=None)
	aparser.add_argument('-p', '--pos', help='Prediction for POS', default=False, action='store_true')
	aparser.add_argument('-t', '--tone', help='Prediction for tones', default=False, action='store_true')
	aparser.add_argument('-g', '--gloss', help='Prediction for gloses', default=False, action='store_true')
	aparser.add_argument('-e', '--evalsize', help='Percent of randomized data to use for evaluation (default 10)', default=10)

	aparser.add_argument('-d', '--disambiguate', help='Use model F to disambiguate data', default=None)
	aparser.add_argument('-i', '--infile' , help='Input file (.html)' , default="sys.stdin")
	aparser.add_argument('-o', '--outfile', help='Output file (.html)', default="sys.stdout")

	args = aparser.parse_args()
	print args

	if args.learn:

		if not (args.pos or args.tone or args.gloss) :
			print 'Choose pos, tone, gloss or combination of them'
			exit(0)

		print 'Make list of files'
		files1 = glob.iglob("../corbama/*/*.dis.html")
		files2 = glob.iglob("../corbama/*.dis.html")
		allfiles = ""
		for file1, file2 in zip(files1, files2):
			allfiles += file1+','+file2+','
		allsents = []

		# verbose :
		if args.tone :
			cnt_non_encodable_tone = 0
			cnt_encodable_tone = 0

		print 'Open files and find features / supervision tags'
		for infile in allfiles.split(','):
			if(len(infile)) :
				print '-', infile
				sent = []

				# in_handler = formats.HtmlReader(infile, compatibility_mode=False) #
				html_parser = FileParser()
				html_parser.read_file(infile)

				# for token in in_handler:
				for snum, sentence in enumerate(html_parser.glosses) :
					for tnum, token in enumerate(sentence[2]) :
						tag = ''
						if token.type == 'w' or token.type == 'c':
							tags = ''
							if args.pos:
								for ps in token.gloss.ps  :
									tags += ps.encode('utf-8')
							if args.tone:
								[tone_coded, validity] = differential_encode(token.token, \
								       				        token.gloss.form, \
												    lists_of_equivalence)

								if validity :
									tags += tone_coded.encode('utf-8')
									cnt_encodable_tone += 1

									if args.verbose :
										if tone_coded :
											sys.stdout.write(u"{} : \'{}\' - \'{}\' = \'{}\'\n".\
											format(cnt_encodable_tone,token.gloss.form,token.token,tone_coded))


								else :
									# tags += token.gloss.form.encode('utf-8')
									cnt_non_encodable_tone += 1
							if args.gloss:
								tags += token.gloss.gloss.encode('utf-8')
							sent.append((token.token, tags))
						# if token.type == 'c' and token.token in ['.', '?', '!']: #
					if len(sent) > 1:
						allsents.append(sent)
						sent = []

		# print allsents # débogage

		# affichage
		if args.verbose and args.tone :
			print ""
			print  'number of tokens encodables     :', cnt_encodable_tone
        	        print  'number of tokens non-encodables :', cnt_non_encodable_tone
			print u'rate of non-coded tones         :', "%4.2f" % ( cnt_non_encodable_tone / float(cnt_encodable_tone) * 100), "%"

		datalength = len(allsents)
		p = (1-args.evalsize/100.0)
		print 'Randomize and split the data in train (', int(p*datalength),' sentences) / test (', int(datalength-p*datalength),' sentences)'
		random.seed(123456)
		random.shuffle(allsents)
		train_set = allsents[:int(p*datalength)]
		test_set = allsents[int(p*datalength):datalength]

		print 'Building classifier (CRF/NLTK)'
		tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
		t1 = time.time()
		tagger.train(train_set, args.learn)
		t2 = time.time()
		texec = t2-t1
		print "... done in",  time.strftime('%H %M %S', time.localtime(texec))

		print 'Evaluating classifier'
		print tagger.evaluate(test_set)

		if args.verbose:
			print 'Compute detailed output'

	else:
		print 'USE...'
		html_parser = FileParser()
		tagger = CRFTagger()
		tagger.set_model_file(args.disambiguate)
		html_parser.read_file(args.infile)

		# construction des données à être étiqueter
		allsents = []
		for sentence in html_parser.glosses :
			sent = []
			for token in sentence[2] :
				sent.append(token.token)
			allsents.append(sent)
		# print allsents

		# étiquettage par CRF
		tagged_sent = tagger.tag_sents(allsents)
		# print tagged_sent

		# sauvergardage
		for snum, sentence in enumerate(html_parser.glosses) :
			#print u"phrase °" + str(snum)
			for tnum, token in enumerate(sentence[2]) :
				#sys.stdout.write(u"\t token °{}:\'{}\', \'{}\'".\
				#	format(tnum,token.token, token.gloss.ps) + "\n")
				if token.value and len(token.value) > 2:
					for nopt, option in enumerate(token.value[2]) :
						pass
					 	#sys.stdout.write(u"\t\t option °{}\'{}\',\'{}\',\'{}\'\n".\
						#	format(nopt, option.ps, option.form, option.gloss))
					# ceci est un exemple qui montre comment intégrer un résultat de désambiguïsation
					# dans un fichier HTML de sortie, en soumettant à l'objet une nouvelle liste des
					# gloses pour chaque token donnée
					#option2 = Gloss(token.token, 'x', '', '')
					ps =  (tagged_sent[snum][tnum][1],)
					# format Gloss (token, pos, glose, morpheme)
					option2 = Gloss(token.token, ps, '', '')
					print option2, option
					html_parser.glosses[snum][1][tnum] = [option2]
			print ""

		html_parser.write(args.outfile)

	exit(0)

if __name__ == '__main__':
	main()

