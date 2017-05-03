#!/usr/bin/python
# -*- coding: utf-8 -*-

# Auteur : Elvis Mboning, Stagiaire 2016, INALCO
# Auteur : Damien Nouvel, MCF, INALCO

# Le principale rôle de ce script est de créer des modèles de données pour l'apprentissage automatique avec CRFTagger.
# Le CRF implémenté provient du module tag de NLTK inspiré de CRFSuite (http://www.nltk.org/api/nltk.tag.html#module-nltk.tag.crf).
# Trois modèles sont possibles : les POS, les tons, les gloses

# todo:
# 1. implémenter un décoder de tones qui consiste à reconstruire la forme tonal à partir du token et le code tonal qui lui est associé
#    par l'encodeur précédemment.
# 2. rapport de statistique plus lisible +
# 4. à propos de l'interface de désambiguisation :
#	mode 3 : afficher la probabilité pour chacun d'une liste des tokens proposés à la place d'un mot d'une phrase
#		 une marginalisation est nécessaire pour obtenir la propabilité d'un choix de token sur une phrase. Le but
#		 est d'ordonner les éléments de chaque liste par leurs probabilités d'apparition en tenant compte du modèle CRF,
#		 qui associe à chaque mot un contexte de phrase, et qui donne l'ensemble des étiquettes pour une phrase
#
# des RDV. prévus
# 	le 9 mai à 12 heures
#	le 10 mai à 15 heures
# 

import sys, re, codecs, glob, time, os
import argparse
import formats,  grammar
import collections
from ntgloss import Gloss
from nltk.tag.crf import CRFTagger
from gdisamb import FileParser
from differential_tone_coding import encoder_tones, chunking, options, lst_vowels
import unicodedata
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

def _get_features_customised_for_tones(tokens, idx):

	feature_list = []

	if not tokens:
		return feature_list

	try :
		token = tokens[idx]
	except IndexError :
		raise

	if token != '_' :

		# positon du syllabe actuel et préfixe et suffixe du même mot
		lst = []
		for i in range(idx, len(tokens) + 1, 1) :
			try :
				if tokens[i] == "_" :
					lst.append(i)
					if len(lst) >= 2 :
						break
			except IndexError :
				lst.append(i)
				break

		if lst :
			feature_list.append("SYLLABE_ID1_" + str(lst[0] - idx))
			try :
				feature_list.append("SUFFIXE_ACTUEL_" + tokens(lst[0] - 1))
			except :
				pass

		lst2 = []
		for i in range(idx, -2, -1) :
			try :
				if tokens[i] == "_" :
					lst2.append(i)
					if len(lst2) >= 2 :
						break
			except IndexError :
				lst2.append(i)
				break

		if lst2 :
			feature_list.append("SYLLABE_ID2_" + str(idx - lst2[0]))
			try :
				feature_list.append("PREFIXE_ACTUEL_" + tokens(lst2[0] + 1))
			except :
				pass

		# préfixe et suffixe du mots précédent et suivant dans la même phrase
		if len(lst) > 1 :
			try :
				prefixe_du_mot_suivant = tokens[lst[0] + 1]
				feature_list.append("PREFIXE_SUIVANT_" + prefixe_du_mot_suivant)
			except IndexError :
				pass
			try :
				suffixe_du_mot_suivant  = tokens[lst[1] - 1]
				feature_list.append("SUFFIXE_SUIVANT_" + suffixe_du_mot_suivant)
			except IndexError :
				pass
			try :
				suffixe_du_mot_precedent = tokens[lst2[0] - 1]
				feature_list.append("SUFFIXE_PRECEDENT_" + suffixe_du_mot_precedent)
			except IndexError:
				pass
			try :
				prefixe_du_mot_precedent = tokens[lst2[1] + 1]
				feature_list.append("PREFIXE_PRECEDENT_" + prefixe_du_mot_precedent)
			except IndexError :
				pass
		
	# Capitalization 
	if token[0].isupper():
		feature_list.append('CAPITALIZATION')

	# Number
	if re.search(r'\d', token) is not None:
		feature_list.append('IL_Y_A_UN_CHIFFRE')
		
	# Punctuation
	punc_cat = set(["Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po"])
	if all (unicodedata.category(x) in punc_cat for x in token):
		feature_list.append('PONCTUATION_PURE')
		
	# Voyelles
	voyelles = ""
	for c in token :
		if c in lst_vowels:
			voyelles += c
	feature_list.append('VOYELLES_'+ voyelles)

	# Syllabes précédent et suivant
	try :
		feature_list.append('SYLLABE_PRECEDENT_' + token[idx - 1])
	except IndexError :
		feature_list.append('SYLLABE_PRECEDENT_NUL')

	try :
		feature_list.append('SYLLABE_SUIVANT_' + token[idx + 1])
	except IndexError :
		feature_list.append('SYLLABE_SUIVANT_NUL')

	feature_list.append('SYLLABE_ACTUEL_' + token)
	
	#
	# Suffix up to length 3
	if len(token) > 1:
		feature_list.append('SUF_' + token[-1:]) 
		feature_list.append('PRE_' + token[:1]) 
	if len(token) > 2: 
		feature_list.append('SUF_' + token[-2:]) 
		feature_list.append('PRE_' + token[:2])    
	if len(token) > 3: 
		feature_list.append('SUF_' + token[-3:])
		feature_list.append('PRE_' + token[:3]) 

	return feature_list

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
	# mode 2 : séléctionne la phrase la plus probable (d'après la CRF) de la liste des glosses
	# mode 3 : présenter toutes les possibilités avec leur probabilité donnée par la CRF

	aparser.add_argument('-i', '--infile' , help='Input file (.html)' , default=sys.stdin)
	aparser.add_argument('-o', '--outfile', help='Output file (.html)', default=sys.stdout)

	# experimental parameters with relation to tone learning
	aparser.add_argument('-s', '--store', help='Store tagged raw data in file (.csv) for research purposes', default=None)
	aparser.add_argument('-R', '--Ratio', help='Percent of total data to use for training and test', default=1)
	aparser.add_argument('-D', '--Debug', help='Verbose output for debug', default=False, action='store_true')
	aparser.add_argument('--no_replacement', help='REMPLACEMENT_INTERDIT', default=False, action='store_true')
	aparser.add_argument('--decompose', help='DECOMPOSE_OPS_FOR_TONES_PAUSE', default=False, action='store_true')
	aparser.add_argument('--no_deleted_caracter', help='NOT_TO_CODE_CARACTER_TO_DELETE', default=False, action='store_true')
	aparser.add_argument('--only_tones', help='ONLY_TONE_PREDICTION', default=False, action='store_true')
	aparser.add_argument('--only_tones_pauses', help='ONLY_TONE_PAUSE_PREDICTION', default=False, action='store_true')
	aparser.add_argument('--shaping_token', help='SHAPING_TOKEN_IN', default=False, action='store_true')

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
					args.no_replacement,\
					args.decompose,\
					args.no_deleted_caracter,\
					args.only_tones,\
					args.only_tones_pauses,\
					args.shaping_token)
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
									if args.verbose and args.Debug:
										sys.stdout.write(u"{} -> {}\n".format(token.token, token.gloss.form))
									chunk_id = 0
									for chunk, code in zip(chunks, codes) :
										if args.verbose and args.Debug:
											sys.stdout.write(u"\tchunk {} : {} -> {}\n".format(chunk_id, chunk, code))
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
			#if args.tone :
			features = [_get_features_customised_for_tones(tokens, i) for i in range(len(tokens))]
			#else :
			#	features = [tagger._get_features(tokens, i) for i in range(len(tokens))]
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
			#if args.tone :
			features = [_get_features_customised_for_tones(tokens,i) for i in range(len(tokens))]
			#else:
			#	features = [tagger._get_features(tokens, i) for i in range(len(tokens))]

			labels = tagger._tagger.tag(features)

			if len(labels) != len(tokens):
				raise Exception(' Predicted Length Not Matched, Expect Errors !')

			tagged_sent = list(zip(tokens,labels))
			tagged_sents.append(tagged_sent)

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
			#if args.tone :
			features = [_get_features_customised_for_tones(tokens,i) for i in range(len(tokens))]
			#else:
			#	features = [tagger._get_features(tokens, i) for i in range(len(tokens))]

			labels = tagger._tagger.tag(features)
			# fonctions à appeler pour les modes 2 & 3
			# tagger._tagger.set(features)
			# tagger._tagger.probability(tags)

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
