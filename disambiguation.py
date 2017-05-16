#!/usr/bin/python
# -*- coding: utf-8 -*-

# Auteur : Elvis Mboning, Stagiaire 2016, INALCO
# Auteur : Damien Nouvel, MCF, INALCO

# Le principale rôle de ce script est de créer des modèles de données pour l'apprentissage automatique avec CRFTagger.
# Le CRF implémenté provient du module tag de NLTK inspiré de CRFSuite (http://www.nltk.org/api/nltk.tag.html#module-nltk.tag.crf).
# Trois modèles sont possibles : les POS, les tons, les gloses

# todo:
# * petit rapport sur les distributions de caractères et leurs natures dans le corpus
## * enregistrement et téléverser
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
from differential_tone_coding import get_features_customised, chunking, encoder_tones, repr, token_seperator, _get_features_customised_for_tones, code_dispatcher, code_resort, mode_indicators
import unicodedata
import pycrfsuite
import csv
import nltk.tag.util
import itertools
from nltk.metrics.scores import accuracy
import zipfile

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

def csv_export2(filename, gold_tokens, test_tokens):

	try :
		csvfile = codecs.open(filename, 'wb')
		writer = csv.writer(csvfile)
		writer.writerow(["Token", "Golden", "Predicted", "Same"])
		for g, t in zip(gold_tokens, test_tokens) :
			token          = g[0]
			golden_code    = g[-1]
			predicted_code = t[-1]
			sameCodes = (golden_code == predicted_code)

			if not repr(token.encode('utf-8')) :
				sameCodes = u''
			row = [\
				repr(token.encode('utf-8')), \
				repr(golden_code, spaces=True), \
				repr(predicted_code, spaces=True), \
				sameCodes]

			writer.writerow(row)
		csvfile.close()
	except :
		raise
		print "unable to dump result in CSV file to create !"


def sampling(allsents, p, ratio = 1) :
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
	aparser.add_argument('-d', '--disambiguate', help='Use model F to disambiguate data, the gloss list will be ordered by the probability growth order', default=None)
	aparser.add_argument('--select', help = 'Option that will be taken into account only with the use of -d, which specifies the disambiguation modality is to select only the most likely gloss in each list.', action='store_true')
	aparser.add_argument('-i', '--infile' , help='Input file (.html)' , default=sys.stdin)
	aparser.add_argument('-o', '--outfile', help='Output file (.html)', default=sys.stdout)
	aparser.add_argument('-s', '--store', help='Store tagged raw data in file (.csv) for further research purpose', default=None)

	args = aparser.parse_args()
	if args.verbose :
		print 'Arguments received by script'
		dico = vars(args)
		for key,val in dico.items():
			typeName = type(val).__name__
			sys.stdout.write("\t{} = {} ".format(key, val))
			if val :
				sys.stdout.write("({})".format(typeName))
			print ""

	if not (args.pos or args.tone or args.gloss) :
			print 'Choose pos, tone, gloss'
			aparser.print_help()
			exit(0)

	if args.learn :
		print 'Make list of files'
		files1 = glob.iglob("../corbama/*/*.dis.html")
		files2 = glob.iglob("../corbama/*.dis.html")

		allfiles = ""
		for file1, file2 in zip(files1, files2):
			allfiles += file1+','+file2+','
		allsents = []

		# pour le débogage
		allfiles = '../corbama/sisoko-daa_ka_kore.dis.html'

		if args.tone :
			try    :
				enc = encoder_tones()
			except :
				enc = None
				print ("Error : unable to initialize the tone encoder !")
				exit()

		print 'Making observation data from disambiggated corpus of which'
		for infile in allfiles.split(','):
			if(len(infile)) :
				sys.stdout.write("\t{}\n".format(infile))
				sent = []

				html_parser = FileParser()
				html_parser.read_file(infile)

				for snum, sentence in enumerate(html_parser.glosses) :
					for tnum, token in enumerate(sentence[2]) :
						if token.type == 'w' or token.type == 'c':
							if args.pos:
								# sent : list(str,str)
								tags = ''
								for ps in token.gloss.ps :
									tags += ps.encode('utf-8')
								sent.append((token.token, tags))
							elif args.tone:
								# sent : list(list(str,str))
								# token2 : list(str,str)
								token2 = []
								forms = token.gloss.form.split('|')
								[codes, syllabes] = enc.differential_encode(token.token, forms[0])
								for code, syllabe in zip(codes, syllabes) :
									token2.append((syllabe, code.encode('utf-8')))
								sent.append(token2)
							elif args.gloss:
								# sent : list(str,str)
								tags = token.gloss.gloss.encode('utf-8')
								sent.append((token.token, tags))

					if len(sent) > 1:
						allsents.append(sent)
						sent = []

		if args.verbose and args.tone :
			enc.report()

		print 'Split the data in '
		p = (1 - args.evalsize / 100.0)
		train_set, eval_set = sampling(allsents, p)
		print '\t train (', len(train_set),' sentences) / test (', len(eval_set),' sentences)'

		print 'Building classifier (pyCRFsuite)'
		# Initialization
		t1 = time.time()
		if args.tone  :
			num_phases = len([False, True]) * len(mode_indicators)
			myzip = zipfile.ZipFile(args.learn + '.zip', 'w')
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

			for sent in train_set :
				if not args.tone :
					# train_set : list(list(str,str)))
					# tokens, labels : list(str)
					tokens = unzip(sent)[0]
					labels = unzip(sent)[1]
					features = [get_features_customised(tokens, i) for i in range(len(tokens))]
				else :
					# train_set : list(list(list(str,str)))
					# tokens : list(list(str))
					# labels : list(list(list(str)))
					labels = list()
					for token in sent :
						label = [code_dispatcher(syllabe.decode('utf-8'))[phase].encode('utf-8') for syllabe in token]
						labels.append(label)

				trainer.append(features, labels)
			trainer.train(model = model_name)

			if num_phases > 1 :
				myzip.write(model_name)
				os.remove(model_name)
		if num_phases > 1 :
			myzip.close()

		print "... done in", get_duration(t1_secs = t1, t2_secs = time.time())

		# Evaluation
		print 'Evaluating classifier'
		# gold_set, predicted_set : list(list((str, str)))
		# input_set, output_gold_set : list(list(str))
		gold_set = eval_set
		input_set = [unzip(sent)[0] for sent in gold_set]
		predicted_set = [list() for sent in gold_set]
		if num_phases > 1 :
			myzip = zipfile.ZipFile(args.learn + '.zip', 'r')
		for phase in range(num_phases) :
			tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
			trainer = pycrfsuite.Trainer(verbose = tagger._verbose)
			trainer.set_params(tagger._training_options)
			if num_phases > 1:
				model_name = args.learn + '.' + str(phase)
				myzip.extract(model_name)
			else :
				model_name = args.learn
			tagger.set_model_file(model_name)
			for i, sent in enumerate(input_set) :
				features = [get_features_customised(sent, j) for j in range(len(sent))]
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
			if num_phases > 1 :
				os.remove(model_name)
		if num_phases > 1 :
			myzip.close()

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

		if args.store :
			stored_filename = args.store
			csv_export2(stored_filename, gold_tokens, predicted_tokens)

		print "Exactitude : {:>5.3f}".format(accuracy(gold_tokens_eval, predicted_tokens_eval))

		if args.verbose and args.store :
			print ("Tagged result is exported in {}".format(args.store))

	elif args.disambiguate and args.infile and args.outfile :
		# Lecture de texte en .HTML
		html_parser = FileParser()
		tagger = CRFTagger()

		if args.pos :
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

			for snum, sentence in enumerate(html_parser.glosses) :
				tokens = [token.token for token in sentence[2]]
				features = [_get_features_customised_for_tones(tokens, i) for i in range(len(tokens))]
				tagger._tagger.set(features)
				for tnum, token in enumerate(sentence[2]) :
					options = list()
					if token.value and len(token.value) > 2:
						for nopt, option in enumerate(token.value[2]) :
							try: tag = option.ps[0]
							except IndexError : tag = ''
							prob = tagger._tagger.marginal(tag, tnum)
							options.append((prob, option))
						reordered_probs, reordered_options = unzip(sorted(options, reverse = True))
						if args.select :
							prob_max = reordered_probs[0]
							reordered_options = tuple([reordered_options[i] for i, p in enumerate(reordered_probs) if p >= prob_max])
						html_parser.glosses[snum][1][tnum] = reordered_options

		elif args.tone :
			try :
				pass
				#tagger.set_model_file(args.disambiguate)
			except IOError:
				print "Error : unable to open the model {} !".format(args.infile)
				exit(1)
			try :
				html_parser.read_file(args.infile)
			except IOError:
				print "Error : unable to open the input file {} !".format(args.infile)
				exit(1)

			try :
				enc = encoder_tones()
			except :
				enc = None
				print ("Error : unable to initialize the tone encoder !")

			# 1. convertir chacune des formes tonales proposées dans une liste en
			# code différentiel, divisé en segments syllabiques -> enc.differential_encode
			for snum, sentence in enumerate(html_parser.glosses) :
				tokens = [token.token for token in sentence[2]]
				features = [_get_features_customised_for_tones(tokens, i) for i in range(len(tokens))]
				#tagger._tagger.set(features)
				x = [chunking(token.token) for token in sentence[2]]
				print x
				for tnum, token in enumerate(sentence[2]) :
					options = list()
					if token.value and len(token.value) > 2:
						for nopt, option in enumerate(token.value[2]) :
							try: tag = option.form
							except IndexError : tag = ''
							if '|' not in option.form :
								[codes, chunks] = enc.differential_encode(token.token, option.form)
							else :
								codes = u""
								chunks = []

							# ici, les codes syllabiques sont désormais disponbiles

						"""
							#prob = tagger._tagger.marginal(tag, tnum)
							options.append((prob, option))
						reordered_probs, reordered_options = unzip(sorted(options, reverse = True))
						if args.select :
							prob_max = reordered_probs[0]
							reordered_options = tuple([reordered_options[i] for i, p in enumerate(reordered_probs) if p >= prob_max])
						html_parser.glosses[snum][1][tnum] = reordered_options
						"""

			# 2. diviser chaque segment syllabique par 4 phases, il s'agit de
			# insertion des alphabets, insertion des marqueurs tonales,
			# suppression des alphabets et suppresion des marqueurs tonales,
			# -> code_dispatcher

			# 3. évaluer la prbabilité de présence de chaque sous-segment syllabico-phsial
			# avec leur modèle respectif -> tagger._tagger.marginal

			# 4. obtenir la probalitié totale en multiplier
			# toutes les 4 probabilités "phasiales"
			# (en supposant que les quatres phases sont statistiquements indépendantes)

			# 5. réordonner la liste par la décroissance de probabilité totale de forme tonales
			# ainsi obtenue


		try : html_parser.write(args.outfile)
		except IOError: print "Error : unable to create the output file {}".format(args.outfile)

	else :
		aparser.print_help()



	exit(0)

if __name__ == '__main__':
	main()
