#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from __future__ import division
from bamana import test,wl,wl_detone
from orthograph import convertw,detone
from morphology import lemmatize, dict_disambiguate, print_gloss
import re

types = list(set([s.lower() for s in set(test.words())]))
types.sort()

wlist = [convertw(w) for w in types if not re.search(r'[0-9.,;:!?]', w)]
wtest = [convertw(w) for w in test.words() if not re.search(r'[0-9.,;:!?]', w)]

def counts(wordlist):
    for word in wordlist:
            stages = -2
            length = []
            result = []
            for form in word:
                if form != detone(form):
                    stage, gl = lemmatize(form, wl)
                else:
                    stage, gl = lemmatize(form,wl_detone)
                if stages < stage:
                    stages = stage
                result.extend(gl)
            length = len(dict_disambiguate(result))
            yield (stages, length, word)

def mean(values):
    return sum(zip(*values)[1], 0.0)/len(values)

ctypes = [c for c in counts(wlist)]
typedict = dict(zip([tuple(i) for i in zip(*ctypes)[2]],ctypes))
twords = [typedict[tuple(w)] for w in wtest]

for ct,lt in [(ctypes,types),(twords,test.words())]:
    nottypes = [i for i in ct if i[0]<0]
    yestypes = [i for i in ct if i[0]>=0]
    infltypes = [i for i in ct if i[0]==0]
    dervtypes = [i for i in ct if i[0]==1]
    reduptypes = [i for i in ct if i[0]==2]
    comptypes = [i for i in ct if i[0]==3]

    print 'Всего в корпусе разных словоформ: {0}\n'.format(len(lt))
    print 'Из них несловарных (числа, пунктуация): {0} ({1:.2f}%)\n'.format(len(types)-len(ct), 100*(len(types)-len(ct))/len(lt))
    print 'Нераспознанных словоформ: {0} ({1:.2f}%) {2:.2f}\n'.format(len(nottypes),100*len(nottypes)/len(ct), mean(nottypes))
    print 'Распознанных словоформ: {0} ({1:.2f}%) {2:.2f}\n'.format(len(yestypes),100*len(yestypes)/len(ct),mean(yestypes))
    print 'Из них:\n'
    print 'Словарь и словоизменительный анализ: {0} ({1:.2f}%) {2:.2f}\n'.format(len(infltypes),100*len(infltypes)/len(ct),mean(infltypes))
    print 'Словообразовательный анализ: {0} ({1:.2f}%) {2}\n'.format(len(dervtypes),len(dervtypes)/len(ct),mean(dervtypes))
    print 'Анализ редупликации: {0} ({1:.2f}%) {2:.2f}\n'.format(len(reduptypes),100*len(reduptypes)/len(ct),mean(reduptypes))
    print 'Анализ композитов: {0} ({1:.2f}) {2:.2f}\n'.format(len(comptypes),100*len(comptypes)/len(ct),mean(comptypes))

