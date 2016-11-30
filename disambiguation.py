#!/usr/bin/python
# -*- coding: utf-8 -*-

# Auteur : Elvis Mboning, Stagiaire 2016, INALCO
# Auteur : Damien Nouvel, MCF, INALCO

# Le principale rôle de ce script est de créer des modèles de données pour l'apprentissage automatique avec CRFTagger.
# Le CRF implémenté provient du module tag de NLTK inspiré de CRFSuite (http://www.nltk.org/api/nltk.tag.html#module-nltk.tag.crf).
# Trois modèles sont possibles : les POS, les tons, les gloses

import sys, re, codecs, random, glob,  time
import argparse
import formats,  grammar
from ntgloss import Gloss
from nltk.tag.crf import CRFTagger
from daba_crf_evaluation import *

import codecs, sys
sys.stdin = codecs.getreader('utf8')(sys.stdin)
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

def main():
    
    aparser = argparse.ArgumentParser(description='Daba disambiguator')
    aparser.add_argument('-t', '--tone', help='Prediction for tones', default=False, action='store_true')
    aparser.add_argument('-g', '--gloss', help='Prediction for gloses', default=False, action='store_true')
    aparser.add_argument('-p', '--modelpos', help='Prediction for POS', default=False, action='store_true')
    aparser.add_argument('-l', '--learn', help='Learn model from data', default=False, action='store_true')
    aparser.add_argument('-u', '--use', help='Use model', default=False, action='store_true')
    aparser.add_argument('-i', '--infile', help='Input file (.html)', default="sys.stdin")
    aparser.add_argument('-o', '--outfile', help='Output file (.html)', default="sys.stdout")
    aparser.add_argument('model', help='The type of data for testing', default=False, nargs='?')
    args = aparser.parse_args()

    if args.use:
        print 'USE...'

    else:
        # Gather all files
        files1 = glob.iglob("../corbama/*/*.dis.html")
        files2 = glob.iglob("../corbama/*.dis.html")
        allfiles = ""
        for file1, file2 in zip(files1, files2):
            allfiles += file1+','+file2+','
        allsents = []

        print 'Open files and find features / supervision tags'
        for infile in allfiles.split(','):
            if(len(infile)) :
                print '-', infile
                sent = []
                in_handler = formats.HtmlReader(infile, compatibility_mode=False)
                for token in in_handler:
                    if token.type == 'w' or token.type == 'c':
                        # CODE FOR POS
                        for ps in token.gloss.ps:
                            sent.append((token.token, ps))
                        # CODE FOR TONE
                        # sent.append((token.token, token.gloss.form.encode('utf-8')))
                        # CODE FOR GLOSS
                        # sent.append((token.token, token.gloss.gloss.encode('utf-8')))
                    if token.type == 'c' and token.token in ['.', '?', '!']:
                        if len(sent) > 1:
                            allsents.append(sent)
                        sent = []

        print 'Split the data in train / evaluation'
        pourcentage = 10;
        datalength = len(allsents)
        train_len = (datalength*pourcentage)/100
        train_set = allsents[:train_len]

        print 'Building CRF classifier (NLTK)'
        tagger = CRFTagger(verbose = True, training_opt = {'feature.minfreq' : 10})
        t1 = time.time()
        tagger.train(train_set, 'disambiguation.model')
        t2 = time.time()
        texec = t2-t1
        print "... done in",  time.strftime('%H %M %S', time.localtime(texec))

    exit(0)

if __name__ == '__main__':
    main()

