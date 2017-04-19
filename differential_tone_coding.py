#! /usr/bin/env python
# coding=utf-8

import unicodedata
import sys
import math
import Levenshtein
from collections import Counter, defaultdict

# todo :

REMPLACEMENT_INTERDIT=True
DECOMPOSE_OPS_FOR_TONES = False
markers_tone =  [unichr(0x0300),unichr(0x0301),unichr(0x0302),unichr(0x030c)]
markers_pause = [unichr(0x002e)]

def entropy2 (dic, cnt, cnt2, mode = 'token', unit = 'natural') :

	# cnt2 : compteur pour la distribution des formes non tonales
	# cnt  : compteur pour la distribution des formes tonales
	# dic  : dicionnaire de correspondance des formes non-tonales à leurs formes tonales

	averaged_entropy = 0.0
	n = 0
	for n, k in enumerate(dic.keys()) :
		lst = dic[k]
		token_cnt = {form_tonal : cnt[form_tonal] for form_tonal in lst}
		if mode == 'occurrence' :
			averaged_entropy += entropy(token_cnt) * cnt2[k]
		else :
			averaged_entropy += entropy(token_cnt)

	averaged_entropy /= float(n + 1)

	if mode == 'occurrence' :
		averaged_entropy /= float(sum(cnt2.values()))

	return averaged_entropy

def entropy (cnt, unit = 'shannon') :

	"""
	Reférence
	http://stackoverflow.com/questions/15450192/fastest-way-to-compute-entropy-in-python
	"""

	base = {
	        'shannon' : 2.,
	        'natural' : math.exp(1),
	        'hartley' : 10.
	}

	if len(cnt) <= 1:
		return 0

	len_data = sum(cnt.values())
	probs = [float(c) / len_data for c in cnt.values()]
	probs = [p for p in probs if p > 0.]
	ent = 0

	for p in probs:
		if p > 0.:
			ent -= p * math.log(p, base[unit])
	return ent


def sprint_cnt(cnt, prefix = "") :
	lst = cnt.most_common()
	return "".join([prefix + itm[0].encode('utf-8') + u' : ' + str(itm[1]).encode('utf-8') + u'\n' for itm in lst if itm])

class statistique () :
	def __init__(self) :
		self.form_non_tonal = Counter()
		self.form_tonal     = Counter()
		self.code           = Counter()
		self.dict_code      = defaultdict()
		self.dict_form_tonal     = defaultdict()
		self.cnt_d = Counter()
		self.cnt_i = Counter()
		self.cnt_r = [Counter(),Counter()]
		self.num            = 0
		self.cnt_ops = 0
		self.mode = Counter()
	def __str__(self) :

		ret  = u""
		ret += u"Entropies globales\n"
		ret += u"\tE(Token sans accents) = {:<6.2f} \n".format(entropy(self.form_non_tonal))
		ret += u"\tE(Forme tonale)       = {:<6.2f} \n".format(entropy(self.form_tonal))
		ret += u"\tE(Code produit)       = {:<6.2f} \n".format(entropy(self.code))
		ret += u"Entropies en moyennes par token quant à la tonalisation\n"
                ret += u"\tE(Tonalisation pour token) = {:<6.2f} (en moyenne) \n".format(entropy2(self.dict_form_tonal,self.form_tonal, self.form_non_tonal))
                ret += u"\tE(Tonalisation pour code)  = {:<6.2f} (en moyenne) \n".format(entropy2(self.dict_code,self.code, self.form_non_tonal))
		ret += u"Distance entre token et sa forme tonale (en moyenne) = {:<6.2f} \n".format(self.cnt_ops / float(self.num))
		ret += u"Distribution des opérations d'édition : \n {}".format(sprint_cnt(self.mode, "\t"))
		ret += u"sur un ensemble de corpus de {} mot(s)\n".format(str(self.num))

		return ret

class encoder_tones () :
	def __init__ (self) :
		self.src = ""
		self.dst = ""
		self.p_src = 0
		self.p_dst = 0
		self.ret = ""

		# statistique sur la complexité
		self.stat = statistique()

	def delete(self) :
		self.ret += '*' + str(self.p_src) + self.src[self.p_src]
		self.stat.cnt_d[self.src[self.p_src]] += 1
		self.stat.cnt_ops += 1
		self.stat.mode["delete"] += 1

	def insert(self) :
		self.ret += '' + str(self.p_src) + self.dst[self.p_dst]
		self.stat.cnt_i[self.dst[self.p_dst]] += 1
		self.stat.cnt_ops += 1
		self.stat.mode["insert"] += 1

	def replace(self) :
		self.ret += '@' + str(self.p_src) + self.dst[self.p_dst]
		self.stat.cnt_r[0][self.src[self.p_src]] += 1
		self.stat.cnt_r[1][self.dst[self.p_dst]] += 1
		self.stat.cnt_ops += 1
		self.stat.mode["replace"] += 1

	def differential_encode (self, form_non_tonal, form_tonal) :

		# init. par codage
		self.ret = ""
		self.p_src = -1
		self.p_dst = -1

		# décomposition du token en opérations d'édition
		self.src = unicodedata.normalize('NFD', form_non_tonal)
		self.dst = unicodedata.normalize('NFD', form_tonal)
		ops = Levenshtein.editops(self.src, self.dst)
		self.stat.form_non_tonal[self.src] += 1
		self.stat.form_tonal    [self.dst] += 1
		self.stat.dict_form_tonal.setdefault(self.src, []).append(self.dst)

		for op in ops :

			mode, self.p_src, self.p_dst = op
			if mode == "delete" :
				self.delete()

			elif mode == "insert" :
				self.insert()

			else : # mode == "replace"
				if REMPLACEMENT_INTERDIT or \
				   self.dst[self.p_dst] in markers_tone or \
   				   self.dst[self.p_dst] in markers_pause and DECOMPOSE_OPS_FOR_TONES :
					self.delete()
					self.insert()
				else :
					self.replace()

		self.stat.num += 1
		self.stat.code[self.ret] += 1
		self.stat.dict_code.setdefault(self.src, []).append(self.ret)
		return self.ret

	# todo:
	# 3. taux de représentation
	def report (self) :
		print self.stat.__str__()

def main () :

	form_non_tonal = u'abécèiè'
	form_tonal     = u'àbèceleh'

	print "src : ", form_non_tonal
	print "dst : ", form_tonal
	enc = encoder_tones()
	print enc.differential_encode (form_non_tonal, form_tonal)
	print enc.differential_encode (form_non_tonal, form_tonal)
	enc.report()

if __name__ == "__main__" : main()
