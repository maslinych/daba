#!/usr/bin/env python3
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

import sys
import codecs
import time
import os
import argparse
import daba.formats
import daba.grammar
import collections
from daba.ntgloss import Gloss
from nltk.tag.crf import CRFTagger
from gdisamb import FileParser
from differential_tone_coding import encoder_tones, repr, token_seperator, _get_features_customised_for_tones, code_dispatcher, code_resort, mode_indicators
import unicodedata
import pycrfsuite
import csv
import nltk.tag.util
import itertools
from nltk.metrics.scores import accuracy
import zipfile
from orthography import detone

sys.stdin = codecs.getreader('utf8')(sys.stdin)
sys.stdout = codecs.getwriter('utf8')(sys.stdout)


def unzip(input):
    return [list(li) for li in zip(*input)]


# dataset : list((str,str))
def getTag(dataset):
    ret = []
    buf = str()
    for data in dataset:
        if data[0] != token_seperator:
            buf += data[1]
        else:
            ret.append(buf)
            buf = str()
    if buf:
        ret.append(buf)
    return ret

def csv_export(enc, filename, gold_tokens, test_tokens):

    try:
        csvfile = codecs.open(filename, 'wb')
        writer = csv.writer(csvfile)
        writer.writerow(["Token", "Golden Form", "Predicted Form", "Golden code", "Predicted code", "Same"])
        for g, t in zip(gold_tokens, test_tokens) :
            token          = g[0]
            golden_code    = g[-1]
            predicted_code = t[-1]
            golden_form    = enc.differential_decode(token, golden_code)
            predicted_form = enc.differential_decode(token, predicted_code)
            sameCodes = (golden_code == predicted_code)
            sameForms = (golden_form == predicted_form)

            if not repr(token) :
                sameCodes = u''
            row = [
                repr(token),
                repr(golden_form),
                repr(predicted_form),
                repr(golden_code, spaces=True),
                repr(predicted_code, spaces=True),
                sameCodes]

            writer.writerow(row)
        csvfile.close()
    except:
        raise
        print("unable to dump result in CSV file to create !")

def sampling(allsents, p, ratio = 1):
    train_set, eval_set = [], []
    for i, sent in enumerate(allsents[0 : : int(1/float(ratio))]) :
        p_approx = float(len(train_set) + 1) / float(len(eval_set) + len(train_set) + 1)
        if p_approx <= p :
            train_set.append(sent)
        else:
            eval_set.append(sent)
    return [train_set, eval_set]

def get_duration(t1_secs, t2_secs):
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
    aparser.add_argument('-r', '--root', help='Corpus root dir')
    aparser.add_argument('-f', '--filelist', help='Path to a list of files to learn from')
    # aparser.add_argument('-g', '--gloss', help='Prediction for gloses', default=False, action='store_true')
    aparser.add_argument('-e', '--evalsize', type=int, default=10,
                         help='Percent of training data with respect to training and test one (default 10)')
    aparser.add_argument('-d', '--disambiguate', help='Use model F to disambiguate data, the gloss list will be ordered by the probability growth order', default=None)
    aparser.add_argument('--select', help = 'Option that will be taken into account only with the use of -d, which specifies the disambiguation modality is to select only the most likely gloss in each list.', action='store_true')
    aparser.add_argument('-i', '--infile' , help='Input file (.html)' , default=sys.stdin)
    aparser.add_argument('-o', '--outfile', help='Output file (.html)', default=sys.stdout)
    aparser.add_argument('-s', '--store', help='Store tagged raw data in file (.csv) for further research purpose', default=None)

    args = aparser.parse_args()
    if args.verbose:
        print(args)

    if args.learn and (args.pos or args.tone or args.gloss):

        if not (args.pos or args.tone or args.gloss):
            print('Choose pos, tone, gloss or combination of them')
            exit(0)

        print('Make list of files')
        allfiles = []
        with codecs.open(args.filelist, 'r', encoding="utf-8") as filelist:
            for line in filelist:
                allfiles.append(line.strip())
        allsents = []

        # pour le débogage
        # allfiles = '../corbama/sisoko-daa_ka_kore.dis.html'

        if args.tone:
            try:
                enc = encoder_tones()
            except:
                enc = None
                print(("Error : unable to initialize the tone encoder !"))

        print('Open files and find features / supervision tags')
        for infile in allfiles:
            if(infile):
                print('-', infile)
                sent = []

                html_parser = FileParser()
                html_parser.read_file(os.path.join(args.root, infile))

                for snum, sentence in enumerate(html_parser.glosses):
                    for tnum, token in enumerate(sentence[2]):
                        tag = ''
                        if token.type == 'w' or token.type == 'c':
                            tags = ''
                            if args.pos:
                                tags = '/'.join(token.gloss.ps)
                                wordform = detone(token.gloss.form)
                                sent.append((wordform, tags))
                            elif args.tone:
                                # Pourquoi ne pas apprendre la forme tonale contenant une barre veticale ?
                                # Parce que dans l'ensemble des corpus désambiguïsés, son occurrence est
                                # au dessous de 10, ce cas de figure semble trop peu fréquent pour apporter
                                # une réélle amélioration dans la modélisation de tonalisation. Néanmoins,
                                # dans la conception du cadre logiciel, rien n'interdit de l'inclure dans
                                # les données d'entraînement et d'en observer le apport
                                if '|' not in token.gloss.form :
                                    [codes, chunks] = enc.differential_encode(token.token, token.gloss.form)
                                    for chunk, code in zip(chunks, codes) :
                                        try : sent.append((chunk, code))
                                        except LookupError: pass
                            """
                            elif args.gloss:
                                tags += token.gloss.gloss
                                sent.append((token.token, tags))
                            """

                    if len(sent) > 1:
                        allsents.append(sent)
                        sent = []

        if args.verbose and args.tone:
            enc.report()

        # Constitution des ensmebles d'entraînement de d'évaluation
        p = (1 - args.evalsize / 100.0)
        train_set, eval_set = sampling(allsents, p)
        print('Split the data in train (', len(train_set),' sentences) / test (', len(eval_set),' sentences)')

        print('Building classifier (CRF/NLTK)')
        # Initialization
        t1 = time.time()
        if args.tone:
            num_phases = len([False, True]) * len(mode_indicators)
            myzip = zipfile.ZipFile(args.learn + '.zip', 'w')
        else:
            num_phases = 1

        # Training
        for phase in range(num_phases):
            tagger = CRFTagger(verbose = args.verbose, training_opt = {'feature.minfreq' : 10})
            trainer = pycrfsuite.Trainer(verbose = tagger._verbose)
            trainer.set_params(tagger._training_options)
            if num_phases > 1:
                model_name = args.learn + '.' + str(phase)
            else:
                model_name = args.learn

            # train_set : list(list((str,list(str))))
            for sent in train_set:
                tokens = unzip(sent)[0]
                labels = unzip(sent)[1]
                if num_phases > 1:
                    for lab in labels:
                        pass
                    labels = [code_dispatcher(label)[phase] for label in labels]
                features = [_get_features_customised_for_tones(tokens, i) for i in range(len(tokens))]
                trainer.append(features, labels)
            trainer.train(model = model_name)
            if num_phases > 1:
                myzip.write(model_name)
                os.remove(model_name)
        if num_phases > 1:
            myzip.close()

        print("... done in", get_duration(t1_secs=t1, t2_secs=time.time()))

        # Evaluation
        print('Evaluating classifier')
        # gold_set, predicted_set : list(list((str, str)))
        # input_set, output_gold_set : list(list(str))
        gold_set = eval_set
        input_set = [unzip(sent)[0] for sent in gold_set]
        predicted_set = [list() for sent in gold_set]
        if num_phases > 1:
            myzip = zipfile.ZipFile(args.learn + '.zip', 'r')
        for phase in range(num_phases):
            tagger = CRFTagger(verbose=args.verbose, training_opt={'feature.minfreq' : 10})
            trainer = pycrfsuite.Trainer(verbose=tagger._verbose)
            trainer.set_params(tagger._training_options)
            if num_phases > 1:
                model_name = args.learn + '.' + str(phase)
                myzip.extract(model_name)
            else:
                model_name = args.learn
            tagger.set_model_file(model_name)
            for i, sent in enumerate(input_set):
                features = [_get_features_customised_for_tones(sent,j) for j in range(len(sent))]
                labels = tagger._tagger.tag(features)
                if num_phases > 1:
                    labels = [code_dispatcher(label)[phase] for label in labels]
                tagged_sent = list(zip(sent, labels))
                if not predicted_set[i]:
                    predicted_set[i] = tagged_sent
                else:
                    sent_acc, labels_acc = unzip(predicted_set[i])
                    labels_acc = [label_acc + label for label_acc, label in zip(labels_acc, labels)]
                    predicted_set[i] = list(zip(sent_acc, labels_acc))
            if num_phases > 1:
                os.remove(model_name)
                myzip.close()

        # gold_tokens, predicted_tokens : list((str,str))
        predicted_tokens = list(itertools.chain(*predicted_set))
        if num_phases > 1:
            predicted_tokens = [
                tuple([pair[0], code_resort(pair[1])])
                for pair in predicted_tokens]
        gold_tokens = list(itertools.chain(*gold_set))
        # gold_tokens_eval, predicted_tokens_eval : list(str)
        if args.tone:
            gold_tokens_eval = getTag(gold_tokens)
            predicted_tokens_eval = getTag(predicted_tokens)
        else:
            gold_tokens_eval = gold_tokens
            predicted_tokens_eval = predicted_tokens

        if args.store and args.tone:
            stored_filename = args.store
            csv_export(enc, stored_filename, gold_tokens, predicted_tokens)

        print("Accuracy : {:>5.3f}".format(accuracy(gold_tokens_eval, predicted_tokens_eval)))

        if args.verbose and args.store:
            print(("Tagged result is exported in {}".format(args.store)))

    elif args.disambiguate and args.infile and args.outfile:
        # Lecture de texte en .HTML
        html_parser = FileParser()
        tagger = CRFTagger()

        if args.pos:
            try:
                tagger.set_model_file(args.disambiguate)
            except IOError:
                print("Error : unable to open the model {} !".format(args.infile))
                exit(1)
            try:
                html_parser.read_file(args.infile)
            except IOError:
                print("Error : unable to open the input file {} !".format(args.infile))
                exit(1)

            # Exportation du résultat de désambiguïsation en .HTML
            for snum, sentence in enumerate(html_parser.glosses):
                tokens = [token.token for token in sentence[2]]
                features = [_get_features_customised_for_tones(tokens, i) for i in range(len(tokens))]
                tagger._tagger.set(features)
                for tnum, token in enumerate(sentence[2]):
                    options = list()
                    if token.value and len(token.value) > 2:
                        for nopt, option in enumerate(token.value[2]):
                            try:
                                tag = option.ps[0]
                            except IndexError:
                                tag = ''
                            prob = tagger._tagger.marginal(tag, tnum)
                            options.append((prob, option))
                        reordered_probs, reordered_options = unzip(sorted(options, reverse = True))
                        if args.select:
                            prob_max = reordered_probs[0]
                            reordered_options = tuple([
                                reordered_options[i]
                                for i, p in enumerate(reordered_probs)
                                if p >= prob_max])
                        html_parser.glosses[snum][1][tnum] = reordered_options

        elif args.tone:
            pass

        try:
            html_parser.write(args.outfile)
        except IOError: print("Error : unable to create the output file {}".format(args.outfile))

    else:
        aparser.print_help()
    exit(0)


if __name__ == '__main__':
    main()
