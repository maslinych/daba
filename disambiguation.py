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


import sys, re, codecs, glob, time, os
import argparse
import formats,  grammar
import collections
from ntgloss import Gloss
from nltk.tag.crf import CRFTagger
from gdisamb import FileParser
from differential_tone_coding import is_a_good_code, code_seperator, get_features_customised, chunking, encoder_tones, repr, get_features_customised_tone, code_dispatcher, code_resort, mode_indicators
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

def accuray2 (dataset1, dataset2, is_tone_mode = False) :
	cnt_sucess = 0
	cnt_fail = 0
	if not is_tone_mode :
		for sent1, sent2 in zip(dataset1, dataset2) :
			for token1, token2 in zip(sent1, sent2) :
				if token1 == token2 :
					cnt_sucess += 1
				else :
					cnt_fail += 1

	else :
		for sent1, sent2 in zip(dataset1, dataset2) :
			for token1, token2 in zip(sent1, sent2) :
				is_identical = True
				for syllabe1, syllabe2 in zip(token1, token2) :
					if syllabe1 != syllabe2 : is_identical = False ; break;
				if is_identical :
					cnt_sucess += 1
				else :
					cnt_fail += 1

	cnt_tot = cnt_sucess + cnt_fail
	if not cnt_tot : return 0.0
	else : return cnt_sucess / float(cnt_tot)

def get_sub_tone_code_of_sentence (sentence, phase) :
	labels = list()
	for i, token in enumerate(sentence) :
		label = list()
		for j, syllabe_code in enumerate(token) :
			syllabe, code = syllabe_code
			subcode = code_dispatcher(code.decode('utf-8'))[phase].encode('utf-8')
			label.append(subcode)
		labels.append(label)
	return labels

def accumulate_tone_code_of_dataset (dataset_acc, dataset) :
	for p, sent in enumerate(dataset_acc) :
		for i, token in enumerate(sent) :
			for j, syllabe_tag_acc in enumerate(token) :
				syllabe_acc, tag_acc = syllabe_tag_acc
				syllabe, tag = dataset[p][i][j]
				if tag_acc and tag :
					tag_acc += code_seperator.encode('utf-8') + tag
				else :
					tag_acc += tag
				dataset_acc[p][i][j] = \
					tuple([syllabe, code_resort(tag_acc.decode('utf-8')).encode('utf-8')])

	return dataset_acc

def reshape_tokens_as_sentnece(tokens, sentnece) :

	ret = list()
	n = 0
	for i, token in enumerate(sentnece) :
		tmp = list()
		for j, syllabe in enumerate(token) :
			tmp.append(tokens[n])
			n += 1
		ret.append(tmp)

	return ret

def make_tokens_from_sentence(sent, is_tone_mode = False) :
	if is_tone_mode :
		tokens = list()
		labels = list()
		for token in sent :
			tokens.append(unzip(token)[0])
			labels.append(unzip(token)[1])
	else :
		tokens = unzip(sent)[0]
		labels = unzip(sent)[1]

	return [tokens, labels]

def make_features_from_tokens(tokens, phase = 0, is_tone_mode = False) :
	if is_tone_mode :
		features_syllabe = list()
		for i, token in enumerate(tokens) :
			feature = list()
			for j, syllabe_code in enumerate(token) :
				feature.append(get_features_customised_tone(tokens, i, j, phase))
			features_syllabe.append(feature)
		features = list(itertools.chain(*features_syllabe))
	else :
		features = list()
		for i in range(len(tokens)) :
			features.append(get_features_customised(tokens, i))
	return features

def inspector_tokens(gold_tokens, predicted_tokens) :
	for x,y in zip(gold_tokens, predicted_tokens) :
		try :
			if x[1] != y[1] :
				print x[0],":",x[1].decode('utf-8'),"->",y[1].decode('utf-8') # ,"(",len(x[1]), len(y[1]),")"
			else :
				print "*",x[0],":",x[1].decode('utf-8'),"->",y[1].decode('utf-8') # ,"(",len(x[1]), len(y[1]),")"
		except :
			print type(x[0]),":",type(x[1]),"->",type(y[1])

def unzip(input) :
	return [list(li) for li in zip(*input)]

def csv_export_tone(enc, filename, gold_tokens, test_tokens):

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

def csv_export(filename, gold_tokens, test_tokens):

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

		# pour le débogage rapide
		allfiles = '../corbama/sisoko-daa_ka_kore.dis.html'
		R = 0.1

		print 'Making observation data from disambiggated corpus of which'
		for infile in allfiles.split(','):
			if infile :
				print '\t', infile

				html_parser = FileParser()
				html_parser.read_file(infile)

				sent = []
				for sentence in html_parser.glosses :
					for token in sentence[2] :
						if token.type == 'w' or \
						   token.type == 'c':
							if args.pos:
								# sent : list(str,str)
								tags = ''
								for ps in token.gloss.ps :
									tags += ps
								sent.append((token.token, tags.encode('utf-8')))
							elif args.tone:
								# sent : list(str,str)
								form = token.gloss.form.split('|')
								tags = form[0]
								sent.append((token.token, tags.encode('utf-8')))

							elif args.gloss:
								# sent : list(str,str)
								tags = token.gloss.gloss
								sent.append((token.token, tags.encode('utf-8')))

					if len(sent) > 1:
						allsents.append(sent)
						sent = []

		if args.tone :
			print 'Token segmentation and Tonal informaiotn compression'
			enc = encoder_tones()
			allsents2 = allsents
			allsents = []
			for sent in allsents2 :
				sent2 = []
				for token_tags in sent :
					token, tags = token_tags
					[codes, syllabes] = enc.differential_encode(token, tags.decode('utf-8'))
					token2 = [(syllabe, code.encode('utf-8')) for syllabe, code in zip(syllabes, codes)]
					sent2.append(token2)
				allsents.append(sent2)

			if args.verbose :
				enc.report()

		p = (1 - args.evalsize / 100.0)
		train_set, eval_set = sampling(allsents, p, R)
		print 'Split the data in \t train (', len(train_set),' sentences) / test (', len(eval_set),' sentences)'

		print 'Building classifier (pyCRFsuite)'
		# Initialization
		t1 = time.time()
		if args.tone :
			num_phases = 2 * len(mode_indicators)
			myzip = zipfile.ZipFile(args.learn + '.zip', 'w')
		else :
			num_phases = 1

		# A. Entrâinement des modèles
		for phase in range(num_phases) :
			# A.1. Initialiser un nouveau modèle CRF
			tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
			trainer = pycrfsuite.Trainer(verbose = tagger._verbose)
			trainer.set_params(tagger._training_options)
			model_name = args.learn
			if args.tone :
				model_name += '.' + str(phase)

			# A.2. Mettre à plat les structures de données pour préparer l'entrâinement contextuel
			for sent in train_set :
				if args.tone :
					[tokens, labels] = make_tokens_from_sentence(sent, args.tone)
					features = make_features_from_tokens(tokens, phase, args.tone)
					labels = get_sub_tone_code_of_sentence(sent, phase)
					labels = list(itertools.chain(*labels))
				else :
					[tokens, labels] = make_tokens_from_sentence(sent, args.tone)
					features = make_features_from_tokens(tokens, 0, args.tone)

				trainer.append(features, labels)
			trainer.train(model = model_name)

			if args.tone :
				myzip.write(model_name)
				os.remove(model_name)

		if args.tone :
			myzip.close()

		print "... done in", get_duration(t1_secs = t1, t2_secs = time.time())

		# B. Evaluation
		print 'Evaluating classifier'
		gold_set = eval_set

		if args.tone :
			myzip = zipfile.ZipFile(args.learn + '.zip', 'r')
			predicted_set_acc = list()
			for phase in range(num_phases) :

				# B.1. Charger le modèle CRF pour une des quatre phases d'annoation tonale
				tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
				trainer = pycrfsuite.Trainer(verbose = tagger._verbose)
				trainer.set_params(tagger._training_options)
				model_name = args.learn + '.' + str(phase)
				myzip.extract(model_name)
				tagger.set_model_file(model_name)

				# B.2 Annotation automatique syllabe par syllabe pour une phrase
				predicted_set = list()
				for p, sent in enumerate(gold_set) :

					[tokens, gold_labels] = make_tokens_from_sentence(sent, args.tone)
					features = make_features_from_tokens(tokens, phase, args.tone)
					labels = tagger._tagger.tag(features)
					labels = reshape_tokens_as_sentnece(labels, sent)

					predicted_tokens = list()
					for i, token in enumerate(sent) :
						predicted_tokens.append(map(list, zip(tokens[i], labels[i])))
					predicted_set.append(predicted_tokens)

				# B.3 Accumuler en ordonner l'annotation syllabique
				if not predicted_set_acc :
					predicted_set_acc = \
						[[[['',''] for syllabe in token] for token in sent] for sent in predicted_set]

				predicted_set_acc = accumulate_tone_code_of_dataset (predicted_set_acc, predicted_set)

			predicted_set = predicted_set_acc


		else :
			# B.1. Charger le modèle CRF pour l'annoation
			tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
			trainer = pycrfsuite.Trainer(verbose = tagger._verbose)
			trainer.set_params(tagger._training_options)
			model_name = args.learn
			tagger.set_model_file(model_name)

			# B.2. Annotation automatique token par token
			predicted_set = list()
			for sent in gold_set :
				[tokens, gold_labels] = make_tokens_from_sentence(sent, args.tone)
				features = make_features_from_tokens(tokens, 0, args.tone)
				labels = tagger._tagger.tag(features)
				predicted_set.append(zip(tokens, labels))

		if args.store :
			stored_filename = args.store
			csv_export(stored_filename, gold_tokens, predicted_tokens)

		print "Accuracy : {:>5.3f}".format(accuray2(gold_set, predicted_set, args.tone))

		if args.verbose and args.store :
			print ("Tagged result is exported in {}".format(args.store))

	elif args.disambiguate and args.infile and args.outfile :

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
				features = [_get_features_customised_tone(tokens, i) for i in range(len(tokens))]
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
			pass

		try : html_parser.write(args.outfile)
		except IOError: print "Error : unable to create the output file {} !".format(args.outfile)

	else :
		aparser.print_help()

	exit(0)

if __name__ == '__main__':
	main()
