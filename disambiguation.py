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
from differential_tone_coding_polyphase import encoder_tones, repr, token_seperator, _get_features_customised_for_tones, code_dispatcher, code_resort, mode_indicators
import unicodedata
import pycrfsuite
import csv
import nltk.tag.util
import itertools
from nltk.metrics.scores import accuracy

import codecs, sys
sys.stdin = codecs.getreader('utf8')(sys.stdin)
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

def unzip(input) :
	return [list(li) for li in zip(*input)]

# dataset : list((str,str))
def getTag(dataset) :
	ret = []
	buf = str()
	for data in dataset :
		if data[0] != token_seperator :
			buf += data[1]
		else :
			ret.append(buf)
			buf = str()
	if buf :
		ret.append(buf)
	return ret

def csv_export(enc, filename, gold_tokens, test_tokens):

	try :
		csvfile = codecs.open(filename, 'wb')
		writer = csv.writer(csvfile)
		writer.writerow(["Token", "Golden Form", "Predicted Form","Golden code", "Predicted code", "Same"])
		for g, t in zip(gold_tokens, test_tokens) :
			token          = g[0]
			golden_code    = g[-1]
			predicted_code = t[-1]
			golden_form    = enc.differential_decode(token, golden_code.decode('utf-8'))
			predicted_form = enc.differential_decode(token, predicted_code.decode('utf-8'))
			sameCodes = (golden_code == predicted_code)
			sameForms = (golden_form == predicted_form)

			if not repr(token.encode('utf-8')) :
				sameCodes = u''
			row = [\
				repr(token.encode('utf-8')), \
				repr(golden_form.encode('utf-8')), \
				repr(predicted_form.encode('utf-8')), \
				repr(golden_code, spaces=True), \
				repr(predicted_code, spaces=True), \
				sameCodes]

			writer.writerow(row)
		csvfile.close()
	except :
		raise
		print "unable to dump result in CSV file to create !"

def sampling(allsents, ratio, p) :
	train_set, eval_set = [], []
	for i, sent in enumerate(allsents[0 : : int(1/float(ratio))]) :
		p_approx = float(len(train_set) + 1) / float(len(eval_set) + len(train_set) + 1)
		if p_approx <= p :
			train_set.append(sent)
		else:
			eval_set.append(sent)
	return [train_set, eval_set]

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
	aparser.add_argument('-P', '--polyphase', help='Polyphase decomposiiton for tone learning', default=False, action='store_true')
	aparser.add_argument('-s', '--store', help='Store tagged raw data in file (.csv) for research purposes', default=None)
	aparser.add_argument('-R', '--Ratio', help='Percent of total data to use for training and test', default=1)
	aparser.add_argument('-D', '--Debug', help='Verbose output for debug', default=False, action='store_true')

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

		allfiles = '../corbama/sisoko-daa_ka_kore.dis.html'

		if args.tone :
			try :
				enc = encoder_tones()
			except :
				enc = None
				print ("error : unable to initialize the tone encoder !")
		# verbose :
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
											chunk_id += 1
										try : sent.append((chunk, code.encode('utf-8')))
										except LookupError: pass
									if args.verbose and args.Debug: print ""

							elif args.gloss:
								tags += token.gloss.gloss.encode('utf-8')
								sent.append((token.token, tags))

					if len(sent) > 1:
						allsents.append(sent)
						sent = []

		if args.verbose :
			if args.tone :
				enc.report()
			print u"Cette expérience porte sur {:>4.2f} % de l'ensembles des corpus diponibles".format(float(args.Ratio)*100.0)
			print ""
			print args
			print ""

		# Constitution des ensmebles d'entraînement de d'évaluation
		p = (1 - args.evalsize / 100.0)
		train_set, eval_set = sampling(allsents, args.Ratio, p)
		print 'Split the data in train (', len(train_set),' sentences) / test (', len(eval_set),' sentences)'

		print 'Building classifier (CRF/NLTK)'

		# Initialization
		t1 = time.time()
		if args.tone and args.polyphase :
			num_phases = len([False, True]) * len(mode_indicators)
		else :
			num_phases = 1

		# Training
		for phase in range(num_phases) :
			tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
			trainer = pycrfsuite.Trainer(verbose = tagger._verbose)
			trainer.set_params(tagger._training_options)
			if num_phases > 1 :
				model_name = args.learn + '.' + str(phase)
			else:
				model_name = args.learn

			# train_set : list(list((str,list(str))))
			for sent in train_set:
				tokens = unzip(sent)[0]
				labels = unzip(sent)[1]
				if num_phases > 1 :
					for lab in labels :
						pass
						# sys.stdout.write(u"[{} -> {}] ".format(lab.decode('utf-8'), code_dispatcher(lab.decode('utf-8'))[phase]))
					labels = [code_dispatcher(label.decode('utf-8'))[phase].encode('utf-8') for label in labels]
				features = [_get_features_customised_for_tones(tokens, i) for i in range(len(tokens))]
				trainer.append(features, labels)
			trainer.train(model = model_name)

		print "... done in", get_duration(t1_secs = t1, t2_secs = time.time())

		# Evaluation
		print 'Evaluating classifier'
		# gold_set, predicted_set : list(list((str, str)))
		# input_set, output_gold_set : list(list(str))
		gold_set = eval_set
		input_set = [unzip(sent)[0] for sent in gold_set]
		predicted_set = [list() for sent in gold_set]
		for phase in range(num_phases) :
			tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
			trainer = pycrfsuite.Trainer(verbose = tagger._verbose)
			trainer.set_params(tagger._training_options)
			if num_phases > 1:
				model_name = args.learn + '.' + str(phase)
			else :
				model_name = args.learn
			tagger.set_model_file(model_name)
			for i, sent in enumerate(input_set) :
				features = [_get_features_customised_for_tones(sent,j) for j in range(len(sent))]
				labels = tagger._tagger.tag(features)
				if num_phases > 1 :
					labels = [code_dispatcher(label.decode('utf-8'))[phase].encode('utf-8') for label in labels]
				tagged_sent = list(zip(sent, labels))
				if not predicted_set[i] :
					predicted_set[i] = tagged_sent
				else :
					sent_acc, labels_acc = unzip(predicted_set[i])
					labels_acc = [label_acc + label for label_acc, label in zip(labels_acc, labels)]
					predicted_set[i] = list(zip(sent_acc, labels_acc))

		# gold_tokens, predicted_tokens : list((str,str))
		predicted_tokens = list(itertools.chain(*predicted_set))
		if num_phases > 1 :
			predicted_tokens = [ tuple([pair[0], code_resort(pair[1].decode('utf-8')).encode('utf-8')]) for pair  in predicted_tokens]
		gold_tokens = list(itertools.chain(*gold_set))
		# gold_tokens_eval, predicted_tokens_eval : list(str)
		if args.tone :
			gold_tokens_eval = getTag(gold_tokens)
			predicted_tokens_eval = getTag(predicted_tokens)
		else :
			gold_tokens_eval = gold_tokens
			predicted_tokens_eval = predicted_tokens

		if args.store and args.tone :
			stored_filename = args.store
			csv_export(enc, stored_filename, gold_tokens, predicted_tokens)

		print "Exactitude : {:>5.3f}".format(accuracy(gold_tokens_eval, predicted_tokens_eval))

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

				tagged_sent = list(zip(tokens, labels))
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

	if args.verbose and args.store :
		print ("Annotated result is exported in")
		stored_filename = args.store
		print ("\t{}".format(stored_filename))

	exit(0)

if __name__ == '__main__':
	main()
