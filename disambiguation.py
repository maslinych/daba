#!/usr/bin/python
# -*- coding: utf-8 -*-

# Auteur : Elvis Mboning, Stagiaire 2016, INALCO
# Auteur : Damien Nouvel, MCF, INALCO

# Le principale rôle de ce script est de créer des modèles de données pour l'apprentissage automatique avec CRFTagger.
# Le CRF implémenté provient du module tag de NLTK inspiré de CRFSuite (http://www.nltk.org/api/nltk.tag.html#module-nltk.tag.crf).
# Trois modèles sont possibles : les POS, les tons, les gloses

# todo:
# * à propos de l'interface de désambiguisation :
#	mode 3 : afficher la probabilité pour chacun d'une liste des tokens proposés à la place d'un mot d'une phrase
#		 une marginalisation est nécessaire pour obtenir la propabilité d'un choix de token sur une phrase. Le but
#		 est d'ordonner les éléments de chaque liste par leurs probabilités d'apparition en tenant compte du modèle CRF,
#		 qui associe à chaque mot un contexte de phrase, et qui donne l'ensemble des étiquettes pour une phrase
# * petit rapport sur les distributions de caractères et leurs natures dans le corpus
# * mode désambiguïsation --order, --select
#   (afin de pouvoir choisir entre la suppression des options et la réordonnance par pertinence des options)
# * réaliser le mode 3
# * expérimentaiton sur l'apprentissage joint du ton et des PdD (POS an anglais)
# * désambiguïsation des tons et de PdD
#
# * enregistrement et téléverser
# * models produits /models/pos_exactitude_0p92.mod
# * models produits /models/tone_exactitude_0p91.mod
# * avec un fihier in et un fichier out
#
# des RDV. prévus
# mercredi 17 mai à 14 : 30

import sys, re, codecs, glob, time, os
import argparse
import formats,  grammar
import collections
from ntgloss import Gloss
from nltk.tag.crf import CRFTagger
from gdisamb import FileParser
from differential_tone_coding import encoder_tones, options, reshaping, repr, token_seperator, _get_features_customised_for_tones
import unicodedata
import pycrfsuite
import csv
import nltk.tag.util
import itertools
from nltk.metrics.scores import accuracy

import codecs, sys
sys.stdin = codecs.getreader('utf8')(sys.stdin)
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

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
	# les trois modes de désambiugisation sont
	# mode 1 : étiquetage par la sortie CRF
	# mode 2 : séléctionner la phrase la plus probable (d'après la CRF) de la liste des glosses
	# mode 3 : présenter toutes les possibilités avec leur probabilité donnée par la CRF puis ordonner la liste

	aparser.add_argument('-i', '--infile' , help='Input file (.html)' , default=sys.stdin)
	aparser.add_argument('-o', '--outfile', help='Output file (.html)', default=sys.stdout)

	# experimental parameters with relation to tone learning
	aparser.add_argument('-s', '--store', help='Store tagged raw data in file (.csv) for research purposes', default=None)
	aparser.add_argument('-R', '--Ratio', help='Percent of total data to use for training and test', default=1)
	aparser.add_argument('-D', '--Debug', help='Verbose output for debug', default=False, action='store_true')
	#aparser.add_argument('--no_replacement', help='REMPLACEMENT_INTERDIT', default=False, action='store_true')
	#aparser.add_argument('--decompose', help='DECOMPOSE_OPS_FOR_TONES', default=False, action='store_true')
	aparser.add_argument('--only_tones', help='ONLY_TONE_PREDICTION', default=False, action='store_true')
	#aparser.add_argument('--shaping_token', help='SHAPING_TOKEN_IN', default=False, action='store_true')

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
				options_obj = options(\
					False,\
					False,\
					args.only_tones,\
					False)
				enc = encoder_tones(options_obj)
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
									if args.verbose and args.Debug :
										sys.stdout.write(u"{} -> {}\n".format(token.token, token.gloss.form))
									chunk_id = 0
									for chunk, code in zip(chunks, codes) :
										if args.verbose and args.Debug:
											sys.stdout.write(u"\tchunk {} : {} -> {}\n".format(chunk_id, chunk, repr(code)))
										try :
											sent.append((chunk, code.encode('utf-8')))

										except LookupError:
											pass
										chunk_id += 1

									if args.verbose and args.Debug:
										print ""
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
		###########################################################
		# code source de la méthode train(train_data, model_file) #
		# de la classe CRFTagger                                  #
		# du parquet nltk.tag.crf                                 #
		#							  #
		# http://www.nltk.org/_modules/nltk/tag/crf.html	  #
		###########################################################
		try :
			trainer = pycrfsuite.Trainer(verbose=tagger._verbose)
		except :
			print ("Error : unable to initialize pycrfsuite !")
		trainer.set_params(tagger._training_options)
		for sent in train_set:
			tokens, labels = zip(*sent)
			features = [_get_features_customised_for_tones(tokens, i) for i in range(len(tokens))]
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
		tagged_sents = []
		for tokens in [nltk.tag.util.untag(sent) for sent in test_set]:
			features = [_get_features_customised_for_tones(tokens,i) for i in range(len(tokens))]
			labels = tagger._tagger.tag(features)

			if len(labels) != len(tokens):
				raise Exception(' Predicted Length Not Matched, Expect Errors !')

			tagged_sent = list(zip(tokens,labels))
			tagged_sents.append(tagged_sent)

		gold_tokens = list(itertools.chain(*test_set))
		test_tokens = list(itertools.chain(*tagged_sents))

		# not to evalute the token seperators
		gold_tokens_eval = []
		test_tokens_eval = []
		gold_buf = ""
		test_buf = ""
		for x,y in zip(gold_tokens, test_tokens) :
			if x[0] != token_seperator :
				gold_buf += x[1]
				test_buf += y[1]
			else :
				gold_tokens_eval.append(gold_buf)
				test_tokens_eval.append(test_buf)
				gold_buf = ""
				test_buf = ""
		if gold_buf :
			gold_tokens_eval.append(gold_buf)
			test_tokens_eval.append(test_buf)

		"""
		paired_tokens = [(g[0], \
				g[-1], \
				test_tokens[i][-1]) \
				for i, g in enumerate(gold_tokens)]
		"""
		# exportation du résultat d'étiquetage en fichier csv
		if args.store :
			if args.tone :
				try :
					csvfile = codecs.open(args.store, 'wb')
					writer = csv.writer(csvfile)
					writer.writerow(["Token", "Golden Form", "Predicted Form","Golden code", "Predicted code", "Same"])
					for g, t in zip(gold_tokens, test_tokens) :
						token = g[0]
						golden_code =  g[-1]
						predicted_code =  t[-1]
						golden_form = enc.differential_decode(token, golden_code.decode('utf-8'))
						predicted_form = enc.differential_decode(token, predicted_code.decode('utf-8'))
						sameCodes = (golden_code == predicted_code)
						sameForms = (golden_form == predicted_form)

						if not repr(token.encode('utf-8')) :
							sameCodes = u''
						row = [\
							repr(token.encode('utf-8')), \
							repr(golden_form.encode('utf-8')), \
							repr(predicted_form.encode('utf-8')), \
							repr(golden_code), \
							repr(predicted_code), \
							sameCodes]

						writer.writerow(row)
						if sameCodes == True and sameForms == False :
							print "Bug !!! "
							print "token", row[0].decode('utf-8')
							print "golden_form", row[1].decode('utf-8')
							print "predicted_form", row[2].decode('utf-8')
							print "golden_code", row[3].decode('utf-8')
							print "predicted_code", row[4].decode('utf-8')
							print "sameCodes",row[5]
							print "sameForms",sameForms
							exit(1)

					csvfile.close()
				except :
					print "unable to dump result in CSV file to create !"
		print accuracy(gold_tokens_eval, test_tokens_eval)

		# affichage avancé
		if args.verbose:
			pass
			# print 'Compute detailed output'

	elif args.disambiguate and args.mode and args.infile and args.outfile and args.pos :

		# Lecture de texte en .HTML
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

		# Étiquetage
		
		# désambiguïsation par la catégorie morphosyntaxique 
		# mode 1 : une désambigïsation qui consiste à utiliser les étiquettes morphosyntaxiques prédites 
		#          par un modèle CRF dont le fichier est précisé, pour ne conserver dans la liste d'options 
		#          de gloses que celles contiennent la catégorie morphsyntaxique renseignée par la CRF
		if int(args.mode) == 1 :
			allsents = []
			for sentence in html_parser.glosses :
				sent = []
				for token in sentence[2] :
					sent.append(token.token)
				allsents.append(sent)

			result = []
			for tokens in allsents:
				features = [_get_features_customised_for_tones(tokens, i) for i in range(len(tokens))]
				labels = tagger._tagger.tag(features)
				if len(labels) != len(tokens):
					raise Exception(' Predicted Length Not Matched, Expect Errors !')

				tagged_sent = list(zip(tokens,labels))
				result.append(tagged_sent)
			tagged_sents = result

			# Exportation du résultat de désambiguïsation en .HTML
			for snum, sentence in enumerate(html_parser.glosses) :
				if args.Debug :
					sys.stdout.write(u"Phrase °" + str(snum) + "\n")
				for tnum, token in enumerate(sentence[2]) :
					if args.Debug :
						sys.stdout.write(u"\t token °{}:\'{}\', \'{}\'".\
							format(tnum,token.token, token.gloss) + "\n")
					options_to_conserve = list()
					ps_predicted =  (tagged_sents[snum][tnum][1].decode('utf-8'),)
					if token.value and len(token.value) > 2:
						for nopt, option in enumerate(token.value[2]) :
							if args.Debug :
								sys.stdout.write(u"\t\t")
							if option.ps == ps_predicted : 
								options_to_conserve.append(option)
								if args.Debug :
									sys.stdout.write('*')
							else : 
								if args.Debug :
									sys.stdout.write(' ')
							if args.Debug :
								sys.stdout.write(u"option °{}\'{}\',\'{}\',\'{}\'\n".\
									format(nopt, option.ps, option.form, option.gloss))
						if options_to_conserve :
							html_parser.glosses[snum][1][tnum] = options_to_conserve
				print ""

			try :
				html_parser.write(args.outfile)
			except IOError:
				print "Error : unable to create the output file {}".format(args.outfile)

		else :
			if args.mode == 2 or args.mode == 3 :
				print ("Warning : modes 2 & 3 in developement ... ")
			else :
				print ("Error : the disambiguation mode you choosed is inexistant !")
				exit(1)

	else :
		aparser.print_help()

	if args.verbose :
		if args.store : print ("result exported in {}".format(args.store))

	exit(0)

if __name__ == '__main__':
	main()
