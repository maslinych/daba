#!/usr/bin/python
# -*- coding: utf-8 -*-

#   from dict_creation import n_grams_freq, multi_freq, annot_pars

from collections import defaultdict

def n_grams_freq(train_set):
    """
        Input
                train_set : list of lists [ [sentence], ... ]
        Return
                d1, d2, d3 : three n-grams dictionaries ; { (n-grams) : frequency }
    """
    d1 = dict() # Unigrams dict
    d2 = dict() # Bigrams dict
    d3 = dict() # Trigrams dict
    for phrase in train_set:
        p = list()
        g = list()
        for i, token in enumerate(phrase):
            p.append(phrase[i][0])
            g.append(phrase[i][1].decode('utf-8'))
        for y, token in enumerate(p):
            d1[(token, g[y])] = d1.get((token, g[y]), 0)+1
            try:
                d2[(token, p[y+1]), (g[y], g[y+1])] = d2.get(((token, p[y+1]), (g[y], g[y+1])), 0)+1
            except IndexError:
                pass
            try:
                d3[(token, p[y+1], p[y+2]), (g[y], g[y+1], g[y+2])] = d3.get(((token, p[y+1], p[y+2]), (g[y], g[y+1], g[y+2])), 0)+1
            except IndexError:
                pass
    return d1, d2, d3

#############################################################################################

def multi_freq(dico):
    """
        Input
                dico : a dictionary ; { (token, gloss) : freqency }
        Return
                dic, a dictionary ; { token : [ [token, gloss, freq], ... ] }
    """
    dic = defaultdict(list)
    for c in dico:
        dic[c[0]].append([c[1], dico[c]])
    return dic

#############################################################################################

def annot_pars(sent, d1, d2, d3):
    """
        Input :
                sent : a list, of one sentence
                d1, d2, d3 : ngrams dictionaries make by n_grams_freq and multi_freq
        Return
                a list of tuples [ (token, annotated_gloss) ]
    """
    new_sent = [u''] * len(sent)
    for i, token in enumerate(sent):
        try:
            maxi = 0
            win = [u''] * 3
            for val in d3[(token, sent[i+1], sent[i+2])]:
                if val[1] > maxi:
                    maxi = val[1]
                    win[0] = val[0][0]
                    win[1] = val[0][1]
                    win[2] = val[0][2]
            new_sent[i] = win[0]
            new_sent[i+1] = win[1]
            new_sent[i+2] = win[2]
        except IndexError:
            pass

    for i, token in enumerate(sent):
        try:
            if new_sent[i] == u'' and new_sent[i+1] == u'':
                maxi = 0
                win = [u''] * 2
                for val in d2[(token, sent[i+1])]:
                    if val[1] > maxi:
                        maxi = val[1]
                        win[0] = val[0][0]
                        win[1] = val[0][1]
                new_sent[i] = win[0]
                new_sent[i+1] = win[1]
        except IndexError:
            pass

    for i, token in enumerate(sent):
        if token.isdigit():
            new_sent[i] = u"CARDINAL"
        else:
            if new_sent[i] == u'':
                maxi = 0
                win = [u'']
                for val in d1[token]:
                    if val[1] > maxi:
                        maxi = val[1]
                        win[0] = val[0]
                new_sent[i] = win[0]

    return zip(sent, new_sent)


