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
from differential_tone_coding_chunking import encoder_tones, chunking

import pycrfsuite
import csv
import nltk.tag.util
import itertools
from nltk.metrics.scores import accuracy

import codecs, sys
sys.stdin = codecs.getreader('utf8')(sys.stdin)
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

def repr (c, null = "None") :
	if not c : return null
	else : return c

def sampling(allsents, ratio, p) :
	train_set, test_set = [], []
	for i, sent in enumerate(allsents[0 : : int(1/float(ratio))]) :
		p_approx = float(len(train_set) + 1) / float(len(test_set) + len(train_set) + 1)
		if p_approx <= p :
			train_set.append(sent)
		else:
			test_set.append(sent)
	return [train_set, test_set]

def get_duration(t1_secs, t2_secs) :
	secs = abs(t1_secs - t2_secs)
	days = secs // 86400
	hours = secs // 3600 - days * 24
	minutes = secs // 60 - hours * 60 - days * 60 * 24
	secondes = int(secs) % 60
	return '{:>02.0f}:{:>02.0f}:{:>02.0f}:{:>02d}'.format(days, hours, minutes, secondes)

def main():

	aparser = argparse.ArgumentParser(description='Daba disambiguator')
	aparser.add_argument('-v', '--verbose', help='Verbose output', default=False, action='store_true')
	aparser.add_argument('-l', '--learn', help='Learn model from data (and save as F if provided)', default=None)
	aparser.add_argument('-p', '--pos', help='Prediction for POS', default=False, action='store_true')
	aparser.add_argument('-t', '--tone', help='Prediction for tones', default=False, action='store_true')
	aparser.add_argument('-g', '--gloss', help='Prediction for gloses', default=False, action='store_true')
	aparser.add_argument('-e', '--evalsize', help='Percent of training data with respect to training and test one (default 10)', default=10)

	aparser.add_argument('-d', '--disambiguate', help='Use model F to disambiguate data', default=None)
	aparser.add_argument('-m', '--mode'        , help='Disambuigation mode' , default=1)
	aparser.add_argument('-i', '--infile' , help='Input file (.html)' , default=sys.stdin)
	aparser.add_argument('-o', '--outfile', help='Output file (.html)', default=sys.stdout)

	# experimental parameters with relation to tone learning
	aparser.add_argument('-a', '--algorithm', help='Optimization algorihtm used for sovling CRF training', default='lbfgs')
	aparser.add_argument('-s', '--store', help='Store tagged raw data in file (.csv) for research purposes', default=None)
	aparser.add_argument('-R', '--Ratio', help='Percent of total data to use for training and test', default=1)
	aparser.add_argument('-c', '--chunksize', help='Size of each chunk of a word', default = 3)

	args = aparser.parse_args()
	if args.verbose :
		print args

	if args.learn and (args.pos or args.tone or args.gloss):

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

		if args.tone :
			try :
				enc = encoder_tones(int(args.chunksize))
			except :
				enc = None
				print ("error : unable to initialize the tone encoder !")
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
								sent.append((token.token, tags))
							elif args.tone:

								if '|' not in token.gloss.form :
									[codes, chunks] = enc.differential_encode(token.token, token.gloss.form)
									for chunk, code in zip(chunks, codes) :
										sent.append((chunk, code.encode('utf-8')))
								else :
									cnt_ambiguity_phonetic += 1
							elif args.gloss:
								tags += token.gloss.gloss.encode('utf-8')
								sent.append((token.token, tags))

					if len(sent) > 1:
						allsents.append(sent)
						sent = []

		if args.verbose :
			if args.tone :
				enc.report()
			print u"Nombre de token ayant une forme tonale phonétiquement variée ou ambiguë :", cnt_ambiguity_phonetic
			print u"Cette expérience porte sur {:>4.2f} % de l'ensembles des corpus diponibles".format(float(args.Ratio)*100.0)
			print ""
			print args
			print ""

		# Constitution des ensmebles d'entraînement de d'évaluation
		p = (1 - args.evalsize / 100.0)
		train_set, test_set = sampling(allsents, args.Ratio, p)
		print 'Split the data in train (', len(train_set),' sentences) / test (', len(test_set),' sentences)'

		print 'Building classifier (CRF/NLTK)'
		tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
		t1 = time.time()

		# Training
		"""
		Set of possible training options (using LBFGS training algorithm).
	         'feature.minfreq' : The minimum frequency of features.
        	 'feature.possible_states' : Force to generate possible state features.
	         'feature.possible_transitions' : Force to generate possible transition features.
	         'c1' : Coefficient for L1 regularization.
	         'c2' : Coefficient for L2 regularization.
	         'max_iterations' : The maximum number of iterations for L-BFGS optimization.
	         'num_memories' : The number of limited memories for approximating the inverse hessian matrix.
	         'epsilon' : Epsilon for testing the convergence of the objective.
	         'period' : The duration of iterations to test the stopping criterion.
	         'delta' : The threshold for the stopping criterion; an L-BFGS iteration stops when the
        	            improvement of the log likelihood over the last ${period} iterations is no greater than this threshold.
	         'linesearch' : The line search algorithm used in L-BFGS updates:
                           { 'MoreThuente': More and Thuente's method,
                              'Backtracking': Backtracking method with regular Wolfe condition,
                              'StrongBacktracking': Backtracking method with strong Wolfe condition
                           }
        	 'max_linesearch' :  The maximum number of trials for the line search algorithm.
		"""
		###########################################################
		# code source de la méthode train(train_data, model_file) #
		# de la classe CRFTagger                                  #
		# du parquet nltk.tag.crf                                 #
		#							  #
		# http://www.nltk.org/_modules/nltk/tag/crf.html	  #
		###########################################################
		# algorithm : {‘lbfgs’, ‘l2sgd’, ‘ap’, ‘pa’, ‘arow’}
		try :
			trainer = pycrfsuite.Trainer(verbose=tagger._verbose, algorithm= args.algorithm)
		except :
			algorithm_list = {'lbfgs', 'l2sgd', 'ap', 'pa', 'arow'}
			if algorithm not in algorithm_list :
				print ("Error : please choose an algorithm among theses possibilities :")
				print (algorithm_list)
			else :
				print ("Error : unable to initialize pycrfsuite !")
		trainer.set_params(tagger._training_options)
		for sent in train_set:
			tokens, labels = zip(*sent)
			features = [tagger._feature_func(tokens, i) for i in range(len(tokens))]
			trainer.append(features, labels)
		trainer.train(model=args.learn)
		tagger.set_model_file(args.learn)

		# on vient de terminer l'entraînement d'un modèle en affichant le temps passé
		print "... done in", get_duration(t1_secs = t1, t2_secs = time.time())

		print 'Evaluating classifier'
		#####################################################
		# code source de la méthode evaluate(gold=test_set) #
		# de la classe TaggerI                              #
		# du parquet nltk.tag.api                           #
		#                                                   #
		# http://www.nltk.org/_modules/nltk/tag/api.html    #
		#####################################################
		tagged_sents = tagger.tag_sents(nltk.tag.util.untag(sent) for sent in test_set)
		gold_tokens = list(itertools.chain(*test_set))
		test_tokens = list(itertools.chain(*tagged_sents))
		paired_tokens = [(g[0], \
				g[-1], \
				test_tokens[i][-1]) \
				for i, g in enumerate(gold_tokens)]

		# exportation du résultat d'étiquetage en fichier csv
		if args.store :
			try :
				csvfile = codecs.open(args.store, 'wb')
				writer = csv.writer(csvfile)
				writer.writerow(["Token", "Golden", "Prediction", "Consistent"])
				for g, t in zip(gold_tokens, test_tokens) :
					row = [\
						repr(g[0].encode('utf-8')), \
						repr(g[-1]), \
						repr(t[-1]), \
						g[-1] == t[-1]]
					writer.writerow(row)
				csvfile.close()
			except :
				print "unable to dump result in CSV file to create !"
		print accuracy(gold_tokens, test_tokens)

		# affichage avancé
		if args.verbose:
			print 'Compute detailed output'

	elif args.disambiguate and args.mode and args.infile and args.outfile :

		html_parser = FileParser()
		tagger = CRFTagger()
		try :
			tagger.set_model_file(args.disambiguate)
		except IOError:
			print "Error : unable to open the model {} !".format(args.infile)
                        exit(1)
		try :
			html_parser.read_file(args.infile)
		except IOError:
			print "Error : unable to open the input file {} !".format(args.infile)
			exit(1)

		# construction des données à être étiqueter
		allsents = []
		for sentence in html_parser.glosses :
			sent = []
			for token in sentence[2] :
				sent.append(token.token)
			allsents.append(sent)

		# étiquettage par CRF
		#######################################################
		# code source de la méthode tag_sents(self, allsents) #
		# de la classe CRFTagger(TaggerI)                     #
		# du parquet nltk.tag.crf                             #
		#                                                     #
		# http://www.nltk.org/_modules/nltk/tag/crf.html      #
		#######################################################
		if tagger._model_file == '':
			raise Exception(' No model file is found !! Please use train or set_model_file function')

		# We need the list of sentences instead of the list generator for matching the input and output
		result = []
		for tokens in allsents:
			features = [tagger._feature_func(tokens,i) for i in range(len(tokens))]
			labels = tagger._tagger.tag(features)

			if len(labels) != len(tokens):
				raise Exception(' Predicted Length Not Matched, Expect Errors !')

			tagged_sent = list(zip(tokens,labels))
			result.append(tagged_sent)
		tagged_sents = result

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
					ps =  (tagged_sents[snum][tnum][1].decode('utf-8'),)
					# format Gloss (token, pos, glose, morpheme)

					# print type(token.token), type(ps[0]); input()

					option2 = Gloss(token.token, ps, '', '')
					print option2, option
					html_parser.glosses[snum][1][tnum] = [option2]
			print ""

		try :
			html_parser.write(args.outfile)
		except IOError:
			print "Error : unable to create the output file {}".format(args.outfile)

	else :
		# show script usage
		aparser.print_help()
	exit(0)

if __name__ == '__main__':
	main()

