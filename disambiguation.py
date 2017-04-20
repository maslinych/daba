#!/usr/bin/python
# -*- coding: utf-8 -*-

# Auteur : Elvis Mboning, Stagiaire 2016, INALCO
# Auteur : Damien Nouvel, MCF, INALCO

# Le principale rôle de ce script est de créer des modèles de données pour l'apprentissage automatique avec CRFTagger.
# Le CRF implémenté provient du module tag de NLTK inspiré de CRFSuite (http://www.nltk.org/api/nltk.tag.html#module-nltk.tag.crf).
# Trois modèles sont possibles : les POS, les tons, les gloses

import sys, re, codecs, glob, time, os
import argparse
import formats,  grammar
import collections
from ntgloss import Gloss
from nltk.tag.crf import CRFTagger
from gdisamb import FileParser
from differential_tone_coding import encoder_tones


import csv
import nltk.tag.util
import itertools
from nltk.metrics.scores import accuracy

import codecs, sys
sys.stdin = codecs.getreader('utf8')(sys.stdin)
sys.stdout = codecs.getwriter('utf8')(sys.stdout)



def main():

	aparser = argparse.ArgumentParser(description='Daba disambiguator')
	aparser.add_argument('-v', '--verbose', help='Verbose output', default=False, action='store_true')
	aparser.add_argument('-l', '--learn', help='Learn model from data (and save as F if provided)', default=None)
	aparser.add_argument('-p', '--pos', help='Prediction for POS', default=False, action='store_true')
	aparser.add_argument('-t', '--tone', help='Prediction for tones', default=False, action='store_true')
	aparser.add_argument('-g', '--gloss', help='Prediction for gloses', default=False, action='store_true')
	aparser.add_argument('-e', '--evalsize', help='Percent of total data to use for evaluation (default 10)', default=10)

	aparser.add_argument('-d', '--disambiguate', help='Use model F to disambiguate data', default=None)
	aparser.add_argument('-i', '--infile' , help='Input file (.html)' , default="sys.stdin")
	aparser.add_argument('-o', '--outfile', help='Output file (.html)', default="sys.stdout")
	aparser.add_argument('-s', '--store', help='Exportation of tagged set in file (.csv) for research purposes', default=None)

	aparser.add_argument('-R', '--Ratio', help='The proportion of the corpus to be processed', default=1)


	args = aparser.parse_args()
	if args.verbose :
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

		enc = encoder_tones()
		# verbose :
		if args.verbose :
			cnt_ambiguity_phonetic = 0
		print 'Open files and find features / supervision tags'
		for infile in allfiles.split(','):
			if(len(infile)) :
				print '-', infile
				sent = []

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

								if '|' not in token.gloss.form :
									tags += enc.differential_encode(token.token, token.gloss.form).encode('utf-8')
								else :
									cnt_ambiguity_phonetic+=1
							if args.gloss:
								tags += token.gloss.gloss.encode('utf-8')

							sent.append((token.token, tags))
					if len(sent) > 1:
						allsents.append(sent)
						sent = []

		if args.verbose :
			if args.tone :
				enc.report()
			print u"Nombre de token ayant une forme tonale phonétiquement variée ou ambiguë :", cnt_ambiguity_phonetic
			print u"Cette expérience porte sur {:>4.2f}% de l'ensembles des corpus diponibles".format(float(args.Ratio)*100.0)
			print ""
			print args
			print ""


		datalength = len(allsents)
		p = (1 - args.evalsize / 100.0)
		print 'Split the data in train (', int(p*datalength),' sentences) / test (', int(datalength-p*datalength),' sentences)'
		# dynamic sampling to split data in train / test set with a percentage p specified
		train_set, test_set = [], []
		for i,sent in enumerate(allsents[0 : : int(1/float(args.Ratio))]) :
			p_approx = (len(train_set) + 1) / (len(test_set) + 1)
			if p_approx <= p :
				train_set.append(sent)
			else:
				test_set.append(sent)

		print 'Building classifier (CRF/NLTK)'
		tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
		t1 = time.time()
		tagger.train(train_set, args.learn)
		t2 = time.time()
		texec = t2 - t1
		days = texec // 86400
		hours = texec // 3600 - days * 24
		minutes = texec // 60 - hours * 60 - days * 60 * 24
		secondes = int(texec) % 60
		print "... done in", '{:>02.0f}:{:>02.0f}:{:>02.0f}:{:>02d}'.format(days, hours, minutes, secondes)

		print 'Evaluating classifier'
		tagged_sents = tagger.tag_sents(nltk.tag.util.untag(sent) for sent in test_set)
		gold_tokens = list(itertools.chain(*test_set))
		test_tokens = list(itertools.chain(*tagged_sents))
		paired_tokens = [(g[0], \
				g[-1], \
				test_tokens[i][-1]) \
				for i, g in enumerate(gold_tokens)]

		# export
		if args.store :
			try :
				csvfile = codecs.open(args.store, 'wb')
				writer = csv.writer(csvfile)
				writer.writerow(["Token", "Golden", "Prediction", "Consistent"])
				for g, t in zip(gold_tokens, test_tokens) :
					writer.writerow([g[0].encode('utf-8'), g[-1], t[-1], (g[-1] == t[-1])])
				csvfile.close()
			except :
				print "unable to dump result in CSV file to create !"
		print accuracy(gold_tokens, test_tokens)

		if args.verbose:
			print 'Compute detailed output'

	else:
		# todo :  sécuriser le mode de désambiguisation en ajoutant des vérifications d'argument
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

		# étiquettage par CRF
		tagged_sent = tagger.tag_sents(allsents)

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

