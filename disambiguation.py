#!/usr/bin/python
# -*- coding: utf-8 -*-

# Auteur : Elvis Mboning, Stagiaire 2016, INALCO
# Auteur : Damien Nouvel, MCF, INALCO
# Auteur : Luigi (Yu-Cheng) Liu, Stagiaire 2017, INALCO
# Auteur : Arthur Provenier, Stagiaire 2017, INALCO (gloss disambiguation)

# Le principale rôle de ce script est de créer des modèles de données pour l'apprentissage automatique avec CRFTagger.
# Le CRF implémenté provient du module tag de NLTK inspiré de CRFSuite (http://www.nltk.org/api/nltk.tag.html#module-nltk.tag.crf).
# Trois modèles sont possibles : les POS, les tons, les gloses

# Gloss can be predict with two differents models :
#   one using CRF (option -g), training is not timewise efficiency and accuracy is uncertain
#   one using n-grams (option -G), faster and more accurate than CRF (~ 10s / accuracy : 0.91)
# Ngrams generated dictionaries are saved with "Pickles" during training and can be called later during disambiguate (option -d)

import sys, re, codecs, glob, time, os, collections, argparse, itertools
import formats,  grammar
from gdisamb import FileParser
from ntgloss import Gloss
from nltk.tag.crf import CRFTagger
import nltk.tag.util
import pycrfsuite
from differential_tone_coding import apply_filter_to_base_element, get_features_customised, get_duration, sampling, csv_export, unzip, encoder_tones, mode_indicators, marginal_tone, accuray2, get_sub_tone_code_of_sentence, accumulate_tone_code_of_dataset, reshape_tokens_as_sentnece, make_tokens_from_sentence, make_features_from_tokens
import unicodedata
import zipfile, ntpath

import fnmatch
sys.stdin = codecs.getreader('utf8')(sys.stdin)
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

from dict_creation import n_grams_freq, multi_freq, annot_pars
import cPickle as pickle

reload(sys)
sys.setdefaultencoding('utf-8')


def main():

    aparser = argparse.ArgumentParser(description='Daba disambiguator')
    aparser.add_argument('-v', '--verbose', help='Verbose output', default=False, action='store_true')
    aparser.add_argument('-l', '--learn', help='Learn model from data (and save as F if provided)', default=None)
    aparser.add_argument('-p', '--pos', help='Prediction for POS', default=False, action='store_true')
    aparser.add_argument('-t', '--tone', help='Prediction for tones', default=False, action='store_true')
    aparser.add_argument('-g', '--gloss', help='Prediction for gloses using CRFsuite', default=False, action='store_true')
    aparser.add_argument('-G', '--Gloss', help='Prediction for gloses using n-grams', default=False, action='store_true')
    aparser.add_argument('-e', '--evalsize', help='Percent of training data with respect to training and test one (default 10)', default=10, type=float)
    aparser.add_argument('-c', '--chunkmode', help='Chunking mode specification which is effective only for tone (default -1)', default=-1, type=int)
    aparser.add_argument('-d', '--disambiguate', help='Use model F to disambiguate data, the gloss list will be ordered by the probability growth order', default=None)
    aparser.add_argument('--select', help = 'Option that will be taken into account only with the use of -d, which specifies the disambiguation modality is to select only the most likely gloss in each list.', action='store_true')

    aparser.add_argument('--filtering', help = 'Experimental option', action='store_true')
    aparser.add_argument('--no_decomposition', help = 'Experimental option', action='store_true')
    aparser.add_argument('--diacritic_only', help = 'Experimental option', action='store_true')
    aparser.add_argument('--non_diacritic_only', help = 'Experimental option', action='store_true')
    aparser.add_argument('--no_coding', help = 'Experimental option', action='store_true')

    aparser.add_argument('-i', '--infile' , help='Input file (.html)' , default=sys.stdin)
    aparser.add_argument('-o', '--outfile', help='Output file (.html)', default=sys.stdout)
    aparser.add_argument('-s', '--store', help='Store evaluation resault in file (.csv) for further research purpose', default=None)

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

    if not (args.pos or args.tone or args.gloss or args.Gloss) :
            print 'Choose pos, tone, gloss'
            aparser.print_help()
            exit(0)

    if args.learn :
        print 'Make list of files'

        """
        files1 = glob.iglob("../corbama/*/*.dis.html")
        files2 = glob.iglob("../corbama/*.dis.html")

        allfiles = ""
        for file1, file2 in zip(files1, files2):
            allfiles += file1+','+file2+','
        """
        allfiles = []
        for root, dirnames, filenames in os.walk('../corbama'):
            for filename in fnmatch.filter(filenames, '*.dis.html'):
                allfiles.append(os.path.join(root, filename))

        allsents = []

        # pour le débogage rapide
        #allfiles = list()
        #allfiles.append(u'../corbama/musokonoma_ka_banaw.dis.html')
        #allfiles.append(u'../corbama/sisoko-daa_ka_kore.dis.html')

        print 'Making observation data from disambiggated corpus of which'
        for infile in allfiles:
            if infile :
                print '\t', infile

                html_parser = FileParser()
                html_parser.read_file(infile)

                sent = []
                for sentence in html_parser.glosses :
                    for token in sentence[2] :
                        if token.type == 'w' or \
                           token.type == 'c':
                            if args.pos and not args.tone and not args.gloss :
                                # sent : list(str,str)
                                tags = ''
                                for ps in token.gloss.ps :
                                    tags += ps
                                sent.append((token.token, tags.encode('utf-8')))
                            elif args.tone and not args.pos and not args.gloss :
                                # sent : list(str,str)
                                form = token.gloss.form.split('|')
                                tags = form[0]
                                sent.append((token.token, tags.encode('utf-8')))
                            elif args.gloss or args.Gloss and not args.tone and not args.pos :
                                # sent : list(str,str)
                                tags = token.gloss.gloss
                                sent.append((token.token, tags.encode('utf-8')))
                            else :
                                print ('Error : multi-modal learning is not yet be supported !')
                                exit()

                    if len(sent) > 1:
                        allsents.append(sent)
                        sent = []

        if args.tone and not args.no_coding :
            print 'Token segmentation and tonal information compression'
            enc = encoder_tones()
            allsents2 = allsents
            allsents = []
            for sent in allsents2 :
                sent2 = []
                for token_tags in sent :
                    token, tags = token_tags
                    [codes, syllabes] = enc.differential_encode(token, tags.decode('utf-8'), args.chunkmode)
                    token2 = [(syllabe, code.encode('utf-8')) for syllabe, code in zip(syllabes, codes)]
                    sent2.append(token2)
                allsents.append(sent2)

            if args.verbose :
                enc.report()

        R = 1 # 1 pour la totalité des corpus
        p = (1 - args.evalsize / 100.0)
        train_set, eval_set = sampling(allsents, p, R)
        print 'Split the data in \t train (', len(train_set),' sentences) / test (', len(eval_set),' sentences)'

        # Initialization
        t1 = time.time()

        if args.Gloss:
            print "Making dictionaries"
            dic_unigram, dic_bigram, dic_trigram = n_grams_freq(train_set)

            if len(dic_unigram) == 0:
                print "Error, -- {} is EMPTY! Exit".format(dic_unigram)
                exit(1)
            if len(dic_bigram) == 0:
                print "Error, -- {} is EMPTY! Exit".format(dic_bigram)
            if len(dic_trigram) == 0:
                print "Error, -- {} is EMPTY! Exit".format(dic_trigram)
                exit(1)

            dic_uni = multi_freq(dic_unigram)
            dic_bi = multi_freq(dic_bigram)
            dic_tri = multi_freq(dic_trigram)
            print "Dictionaries created"

            with open(args.learn, "wb") as F_OUT:
                pickle.dump( (dic_uni, dic_bi, dic_tri), F_OUT )

        else:
            print 'Building classifier (pyCRFsuite)'
            if args.tone and not args.no_coding :
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
                if args.tone and not args.no_coding :
                    if args.diacritic_only and (phase == 0 or phase == 1) :
                        continue
                    if args.non_diacritic_only and (phase == 2 or phase == 3) :
                        continue
                    elif args.no_decomposition and phase % len(mode_indicators) != 0 :
                        continue
                    model_name += '.' + str(phase)

                # A.2. Mettre à plat les structures de données pour préparer l'entrâinement contextuel
                for sent in train_set :
                    if args.tone and not args.no_coding :
                        [tokens, labels] = make_tokens_from_sentence(sent, args.tone and not args.no_coding)
                        features = make_features_from_tokens(tokens, phase, args.tone and not args.no_coding)
                        labels = get_sub_tone_code_of_sentence(sent, phase, sel_en = args.filtering, decomposition_en = not args.no_decomposition)
                        labels = list(itertools.chain(*labels))
                    else :
                        [tokens, labels] = make_tokens_from_sentence(sent, args.tone and not args.no_coding)
                        features = make_features_from_tokens(tokens, 0, args.tone and not args.no_coding)

                    trainer.append(features, labels)
                trainer.train(model = model_name)

                if args.tone and not args.no_coding :
                    myzip.write(model_name)
                    os.remove(model_name)

            if args.tone and not args.no_coding :
                myzip.close()

        print "... done in", get_duration(t1_secs = t1, t2_secs = time.time())

        # B. Evaluation
        print 'Evaluating classifier'
        gold_set = eval_set

        if args.Gloss:
            predicted_set = list()
            for i, sentences in enumerate(eval_set):
                sent = list()
                for y, token in enumerate(sentences):
                    sent.append(token[0])
                predicted_set.append(annot_pars(sent, dic_uni, dic_bi, dic_tri))


            #predicted_set = eval_annot(eval_set, dic_uni, dic_bi, dic_tri)
        else:
            if args.tone and not args.no_coding :
                myzip = zipfile.ZipFile(args.learn + '.zip', 'r')
                predicted_set_acc = list()
                for phase in range(num_phases) :

                    # B.1. Charger le modèle CRF pour une des quatre phases d'annoation tonale
                    tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
                    trainer = pycrfsuite.Trainer(verbose = tagger._verbose)
                    trainer.set_params(tagger._training_options)
                    model_basename = ''
                    for m in myzip.namelist() :
                        if m.endswith(str(phase)):
                            model_basename = m
                            break
                    if not model_basename :
                        continue
                    if args.diacritic_only and (phase == 0 or phase == 1) :
                        continue
                    if args.non_diacritic_only and (phase == 2 or phase == 3):
                        continue
                    elif args.no_decomposition and phase % len(mode_indicators) != 0 :
                        continue

                    myzip.extract(model_basename)
                    tagger.set_model_file(model_basename)
                    os.remove(model_basename)

                    # B.2 Annotation automatique syllabe par syllabe pour une phrase
                    predicted_set = list()
                    for p, sent in enumerate(gold_set) :

                        [tokens, gold_labels] = make_tokens_from_sentence(sent, args.tone and not args.no_coding)
                        features = make_features_from_tokens(tokens, phase, args.tone and not args.no_coding)
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
                    [tokens, gold_labels] = make_tokens_from_sentence(sent, args.tone and not args.no_coding)
                    features = make_features_from_tokens(tokens, 0, args.tone and not args.no_coding)
                    labels = tagger._tagger.tag(features)
                    predicted_set.append(zip(tokens, labels))


            if args.tone and not args.no_coding :
                # on ajuste l'évaluation dans les cas d'apprentissage partiel
                # en nous proposant de filtrer les caractères ignorés par l'apprentissage
                # sinon, nous obtiendrons un résultat pénalisé
                # en voulant comparer une forme prédite partiellement à la forme tonale intégrale d'un même token
                if args.diacritic_only :
                    gold_set = apply_filter_to_base_element(gold_set, [2,3], sel_en = args.filtering, decomposition_en = not args.no_decomposition)
                elif args.non_diacritic_only :
                    gold_set = apply_filter_to_base_element(gold_set, [0,1], sel_en = args.filtering, decomposition_en = not args.no_decomposition)
                elif args.filtering :
                    gold_set = apply_filter_to_base_element(gold_set, [0,1,2,3], sel_en = args.filtering, decomposition_en = not args.no_decomposition)

                """
                if args.verbose :
                    verify(gold_set)
                """

        print "Accuracy : {:>5.3f}".format(accuray2(gold_set, predicted_set, args.tone and not args.no_coding))

        if args.store :
            stored_filename = args.store
            csv_export(stored_filename, gold_set, predicted_set, args.tone and not args.no_coding)

        if args.verbose and args.store :
            print ("Tagged result is exported in {}".format(args.store))

    elif args.disambiguate and args.infile and args.outfile :

        html_parser = FileParser()
        tagger = CRFTagger()

        if args.pos :
            try :
                tagger.set_model_file(args.disambiguate)
            except IOError:
                print "Error : unable to open the model {} !".format(args.disambiguate)
                exit(1)
            try :
                html_parser.read_file(args.infile)
            except IOError:
                print "Error : unable to open the input file {} !".format(args.infile)
                exit(1)

            for snum, sentence in enumerate(html_parser.glosses) :
                tokens = [token.token for token in sentence[2]]
                features = [get_features_customised(tokens, i) for i in range(len(tokens))]
                tagger._tagger.set(features)
                for tnum, token in enumerate(sentence[2]) :
                    options = list()
                    if token.value and len(token.value) > 2:
                        for nopt, option in enumerate(token.value[2]) :
                            try: tag = option.ps[0]
                            except : tag = ''
                            try:
                                prob = tagger._tagger.marginal(tag, tnum)
                            except :
                                prob = 0.0
                            options.append((prob, option))
                        reordered_probs, reordered_options = unzip(sorted(options, key = lambda x : x[0], reverse = True))
                        if args.select :
                            prob_max = reordered_probs[0]
                            reordered_options = tuple([reordered_options[i] for i, p in enumerate(reordered_probs) if p >= prob_max])

                        html_parser.glosses[snum][1][tnum] = reordered_options

        elif args.tone and not args.no_coding :
            try :
                html_parser.read_file(args.infile)
            except IOError:
                print "Error : unable to open the input file {} !".format(args.infile)
                exit(1)
            try :
                if re.search(u"\.zip", args.disambiguate):
                    myzip = zipfile.ZipFile(args.disambiguate,'r')
                else:
                    myzip = zipfile.ZipFile(args.disambiguate + '.zip', 'r')
            except IOError:
                print "Error : unable to open the model file {} !".format((args.disambiguate + '.zip'))
                exit(1)

            num_phases = 2 * len(mode_indicators)
            taggers = []
            enc = encoder_tones()
            for phase in range(num_phases) :
                taggers.append(CRFTagger())
                model_basename = ''
                for m in myzip.namelist() :
                    if m.endswith(str(phase)):
                        model_basename = m
                        break
                if not model_basename :
                    continue
                if args.diacritic_only and (phase == 0 or phase == 1) :
                    continue
                if args.non_diacritic_only and (phase == 2 or phase == 3):
                    continue
                elif args.no_decomposition and phase % len(mode_indicators) != 0 :
                    continue

                myzip.extract(model_basename)
                taggers[phase].set_model_file(model_basename)
                os.remove(model_basename)
            myzip.close()

            for snum, sentence in enumerate(html_parser.glosses) :
                tokens = [enc.differential_encode(token.token, token.token, args.chunkmode)[1] for token in sentence[2]]
                for phase in range(num_phases) :
                    features = make_features_from_tokens(tokens, phase, args.tone and not args.no_coding)
                    if taggers[phase]._model_file :
                        taggers[phase]._tagger.set(features)
                for tnum, token in enumerate(sentence[2]) :
                    options = list()
                    if token.value and len(token.value) > 2:
                        for nopt, option in enumerate(token.value[2]) :
                            try: tag = option.form.encode('utf-8')
                            except : tag = ''
                            prob = marginal_tone(taggers, tnum, tokens, tag, token.token, args.chunkmode, sel_en = args.filtering, decomposition_en = not args.no_decomposition)
                            options.append((prob, option))

                        reordered_probs, reordered_options = unzip(sorted(options, key = lambda x : x[0], reverse = True))
                        if args.select :
                            prob_max = reordered_probs[0]
                            reordered_options = tuple([reordered_options[i] for i, p in enumerate(reordered_probs) if p >= prob_max])
                        html_parser.glosses[snum][1][tnum] = reordered_options

        elif args.Gloss:
            try :
                print u"Loading model : {}".format(args.disambiguate)
                with open(args.disambiguate, "rb") as F_IN:
                    d1, d2, d3 = pickle.load(F_IN)
            except IOError:
                print u"Error : unable to open the model {} !".format(args.disambiguate)
                exit(1)
            try :
                print u"Reading file : {}".format(args.infile)
                html_parser.read_file(args.infile)
            except IOError:
                print u"Error : unable to open the input file {} !".format(args.infile)
                exit(1)

            for snum, sentence in enumerate(html_parser.glosses) :
                sent = list() # Each sentence
                for tnum, token in enumerate(sentence[2]):
                    if token.type == 'w' or token.type == 'c':
                        sent.append(token.token)

                # sent_annot = [(token, gloss), (), ...]
                sent_annot = annot_pars(sent, d1, d2, d3)

                cpt = 0
                for tnum, token in enumerate(sentence[2]):
                    if token.type == 'w' or token.type == 'c':
                        options = list()
                        if token.value and len(token.value) > 2:
                            for nopt, option in enumerate(token.value[2]) :
                                if option.gloss == sent_annot[cpt][1]:
                                    prob = 1
                                else:
                                    prob = 0.0
                                options.append((prob, option))
                            reordered_probs, reordered_options = unzip(sorted(options, key = lambda x : x[0], reverse = True))

                            if args.select :
                                prob_max = reordered_probs[0]
                                reordered_options = tuple([reordered_options[i] for i, p in enumerate(reordered_probs) if p >= prob_max])

                            html_parser.glosses[snum][1][tnum] = reordered_options
                        cpt += 1
            print u"File disambiguated"


        elif args.gloss:
            try :
                print u"Loading model : {}".format(args.disambiguate)
                tagger.set_model_file(args.disambiguate)
            except IOError:
                print u"Error : unable to open the model {} !".format(args.disambiguate)
                exit(1)
            try :
                print u"Reading file : {}".format(args.infile)
                html_parser.read_file(args.infile)
            except IOError:
                print u"Error : unable to open the input file {} !".format(args.infile)
                exit(1)

            for snum, sentence in enumerate(html_parser.glosses) :
                tokens = [token.token for token in sentence[2]]
                features = [get_features_customised(tokens, i) for i in range(len(tokens))]
                tagger._tagger.set(features)
                for tnum, token in enumerate(sentence[2]) :
                    options = list()
                    if token.value and len(token.value) > 2:
                        for nopt, option in enumerate(token.value[2]) :
                            try:
                                tag = option.gloss
                            except :
                                tag = ''
                            try:
                                prob = tagger._tagger.marginal(tag, tnum)
                            except :
                                prob = 0.0
                            options.append((prob, option))
                        reordered_probs, reordered_options = unzip(sorted(options, key = lambda x : x[0], reverse = True))
                        if args.select :
                            prob_max = reordered_probs[0]
                            reordered_options = tuple([reordered_options[i] for i, p in enumerate(reordered_probs) if p >= prob_max])

                        html_parser.glosses[snum][1][tnum] = reordered_options

        try :
            html_parser.write(args.outfile)
            print u"Disambiguated result for {} is saved in {}".format(args.infile, args.outfile)
        except IOError:
            print u"Error : unable to create the output file {} !".format(args.outfile)

    else :
        aparser.print_help()

    exit(0)

if __name__ == '__main__':
    main()
