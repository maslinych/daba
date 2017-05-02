#! /usr/bin/env python
# coding=utf-8

import sys, math, unicodedata
from collections import Counter, defaultdict
import Levenshtein
from syllables import syllabify

# Installation of prerequisites
# sudo pip install python-Levenshtein

# todo :
# implement a new version of tone decoder

# Constant lists
markers_tone  = [unichr(0x0300),unichr(0x0301),unichr(0x0302),unichr(0x030c)]
markers_pause = [unichr(0x002e)]
lst_vowels                 = u'aeiouɛəɑœɔø'
lst_mode_position_caracter = u'$£§#@%'
mode_id_lst           = ["delete","insert","replace"]
caracter_category_lst = ["vowel", "non-vowel"]

""" mode - positon indicator coding
lst_mode_position_caracter[0] <-> a vowel to delete
lst_mode_position_caracter[1] <-> a caracter to insert after a vowel
lst_mode_position_caracter[2] <-> a caracter to be replace after a vowel
lst_mode_position_caracter[3] <-> a non-vowel to delete
lst_mode_position_caracter[4] <-> a caracter to insert after non-vowel
lst_mode_position_caracter[5] <-> a caracter to replace after a non-vowel
"""

# Turning Options
class options() :
	def __init__(self, \
		REMPLACEMENT_INTERDIT          = False,\
		DECOMPOSE_OPS_FOR_TONES_PAUSE  = False,\
		NOT_TO_CODE_CARACTER_TO_DELETE = False,\
		ONLY_TONE_PREDICTION           = False,\
		ONLY_TONE_PAUSE_PREDICTION     = False,\
		SHAPING_TOKEN_IN               = False) :
		self.REMPLACEMENT_INTERDIT = REMPLACEMENT_INTERDIT
		self.DECOMPOSE_OPS_FOR_TONES_PAUSE = DECOMPOSE_OPS_FOR_TONES_PAUSE
		self.NOT_TO_CODE_CARACTER_TO_DELETE = NOT_TO_CODE_CARACTER_TO_DELETE
		self.ONLY_TONE_PREDICTION = ONLY_TONE_PREDICTION
		self.ONLY_TONE_PAUSE_PREDICTION = ONLY_TONE_PAUSE_PREDICTION
		self.SHAPING_TOKEN_IN = SHAPING_TOKEN_IN


def chunking (token) :

	chunks = []
	for chunk in syllabify(token)[0]:
		chunks.append(unicodedata.normalize('NFD', chunk))

	return chunks

def reshaping (token, strip_tones = True) :

	"""
	référence :
	http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
	"""
        token = unicodedata.normalize('NFD', token)

	if strip_tones :
		token = u"".join(c for c in token if unicodedata.category(c) != 'Mn')

	return token.lower()

def get_mode_position_table () :

	ret = ""
	len_mode_id_lst = len(mode_id_lst)
	len_caracter_category = len(caracter_category_lst)
	for j in range(len_caracter_category) :
		for i in range(len_mode_id_lst) :
			ret += " ".join([lst_mode_position_caracter[i + len_mode_id_lst * j], "<->", \
				mode_id_lst[i], "+", caracter_category_lst[j], "\n"])
	return ret

def mode_position_encoder (token, position, mode_id, chunks, offset = 0, lst = lst_vowels) :

	position_eff = position + offset

	position_vowels = 0
	position_others = 0
	position_token = 0
	chunk_id = 0
	chunk_position = 0
	for c in token :
		if c in lst :
			caracter_category_id = 0
			if position_token >= position_eff:
				mp_code = lst_mode_position_caracter[caracter_category_id * len(mode_id_lst) + mode_id] + str(position_vowels)
				return [mp_code, chunk_id]
			position_vowels += 1
		else :
			caracter_category_id = 1
			if position_token >= position_eff:
				mp_code = lst_mode_position_caracter[caracter_category_id * len(mode_id_lst) + mode_id] + str(position_others)
				return [mp_code, chunk_id]
			position_others += 1
		position_token += 1
		chunk_position += 1
		if chunk_position >= len(chunks[chunk_id]):
			chunk_id += 1
			chunk_position = 0
			position_vowels = 0
			position_others = 0
	return [None, None]

def entropy2 (dic, cnty, cntx, mode = 'token', unit = 'shannon') :

	# cntx : compteur pour la distribution des tokens
	# cnty : compteur pour la distribution des formes tonales
	# dic  : dicionnaire de correspondances entre chacun (en string)
	# 	 des tokens et la liste contenant chacune de ses formes tonales

	averaged_entropy = 0.0
	n = 0
	for n, token in enumerate(dic.keys()) :
		forms = dic[token]
		form_cnt = {form_tonal : cnty[form_tonal] for form_tonal in forms}
		if mode == 'occurrence' :
			averaged_entropy += entropy(form_cnt, unit) * cntx[token]
		else : # mode == "token"
			averaged_entropy += entropy(form_cnt, unit)

	averaged_entropy /= float(n + 1)

	if mode == 'occurrence' :
		averaged_entropy /= float(sum(cntx.values()))

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
	def __init__(self, options) :
		self.form_non_tonal = Counter()
		self.form_tonal     = Counter()
		self.code           = Counter()
		self.dict_code      = defaultdict()
		self.dict_form_tonal= defaultdict()
		self.num   = 0
		self.cnt_ops = 0
		self.mode = Counter()
		self.options = options
	def __str__(self) :

		ret  = u""
		ret += u"Entropies globales\n"
		ret += u"\tE(Token)        = {:<6.2f} \n".format(entropy(self.form_non_tonal))
		ret += u"\tE(Forme tonale) = {:<6.2f} \n".format(entropy(self.form_tonal))
		ret += u"\tE(Code produit) = {:<6.2f} \n".format(entropy(self.code))
		ret += u"Entropies par token (en moyenne)\n"
                ret += u"\tE(Forme tonale) = {:<6.2f} \n".\
			format(entropy2(self.dict_form_tonal, cnty = self.form_tonal, cntx = self.form_non_tonal))
                ret += u"\tE(Code produit) = {:<6.2f} \n".\
			format(entropy2(self.dict_code, cnty = self.code, cntx = self.form_non_tonal))
		ret += u"Distance entre une forme tonale et son token (en moyenne) = {:<6.2f} \n".format(self.cnt_ops / float(self.num))
		ret += u"Distribution des opérations d'édition : \n {}".format(sprint_cnt(self.mode, "\t"))
		ret += u"sur un ensemble de corpus de {} mot(s)\n".format(str(self.num))
		ret += u"\nConfigurations\n"
		ret += u"\tREMPLACEMENT_INTERDIT          = {}\n".format(self.options.REMPLACEMENT_INTERDIT)
		ret += u"\tDECOMPOSE_OPS_FOR_TONES_PAUSE  = {}\n".format(self.options.DECOMPOSE_OPS_FOR_TONES_PAUSE)
		ret += u"\tNOT_TO_CODE_CARACTER_TO_DELETE = {}\n".format(self.options.NOT_TO_CODE_CARACTER_TO_DELETE)
		ret += u"\tONLY_TONE_PREDICTION           = {}\n".format(self.options.ONLY_TONE_PREDICTION)
		ret += u"\tONLY_TONE_PAUSE_PREDICTION     = {}\n".format(self.options.ONLY_TONE_PAUSE_PREDICTION)
		ret += u"\tSHAPING_TOKEN_IN               = {}\n".format(self.options.SHAPING_TOKEN_IN)
		return ret

class encoder_tones () :

	def __init__ (self, options) :
		self.src = ""
		self.dst = ""
		self.p_src = 0
		self.p_dst = 0
		self.ret = ""
		self.chunks = []
		self.options = options
		self.stat = statistique(options)

	def delete(self) :
		mode_id = mode_id_lst.index("delete")
		[mp_code, chunk_id] = mode_position_encoder(self.src,self.p_src, mode_id, self.chunks)
		self.ret[chunk_id] += mp_code
		if not self.options.NOT_TO_CODE_CARACTER_TO_DELETE :
			self.ret[chunk_id] += self.src[self.p_src]
		self.stat.cnt_ops += 1
		self.stat.mode["delete"] += 1

	def insert(self) :
		mode_id = mode_id_lst.index("insert")
		[mp_code, chunk_id] = mode_position_encoder(self.src,self.p_src, mode_id, self.chunks, offset = -1)
		self.ret[chunk_id] += mp_code + self.dst[self.p_dst]
		self.stat.cnt_ops += 1
		self.stat.mode["insert"] += 1

	def replace(self) :
		mode_id = mode_id_lst.index("replace")
		[mp_code, chunk_id] = mode_position_encoder(self.src,self.p_src, mode_id, self.chunks)
		self.ret[chunk_id] += mp_code + self.dst[self.p_dst]
		self.stat.cnt_ops += 1
		self.stat.mode["replace"] += 1

	def differential_encode (self, form_non_tonal, form_tonal, seperator = True) :

		self.p_src = -1
		self.p_dst = -1

		if self.options.SHAPING_TOKEN_IN :
			self.src = reshaping(form_non_tonal)
		else:
			self.src = form_non_tonal.lower()

		if not self.src :
			if seperator:
				return [u"_", [u"_"]]
			else :
				return [u"", []]

		self.chunks = chunking(self.src)
		self.ret = [u"" for i in range(len(self.chunks))]

		self.dst = unicodedata.normalize('NFD', form_tonal.lower())
		ops = Levenshtein.editops(self.src, self.dst)
		self.stat.form_non_tonal[self.src] += 1
		self.stat.form_tonal    [self.dst] += 1
		self.stat.dict_form_tonal.setdefault(self.src, []).append(self.dst)

		for op in ops :

			mode, self.p_src, self.p_dst = op
			if mode == "delete" :
				if not self.options.ONLY_TONE_PREDICTION :
					self.delete()

			elif mode == "insert" :
				if not self.options.ONLY_TONE_PREDICTION or \
				      (self.options.ONLY_TONE_PREDICTION and (self.dst[self.p_dst] in markers_tone)) or \
  				      (self.options.ONLY_TONE_PAUSE_PREDICTION and (self.dst[self.p_dst] in markers_tone and \
								       self.dst[self.p_dst] in markers_pause)) :
					self.insert()

			else : # mode == "replace"
				if not self.options.ONLY_TONE_PREDICTION or \
				      (self.options.ONLY_TONE_PREDICTION and (self.dst[self.p_dst] in markers_tone)) or \
  				      (self.options.ONLY_TONE_PAUSE_PREDICTION and (self.dst[self.p_dst] in markers_tone and \
			                                               self.dst[self.p_dst] in markers_pause)) :

					if self.options.REMPLACEMENT_INTERDIT or \
					   ((self.dst[self.p_dst] in markers_tone or \
   					     self.dst[self.p_dst] in markers_pause) and self.options.DECOMPOSE_OPS_FOR_TONES_PAUSE) :

						self.delete()
						self.insert()
					else :
						self.replace()

		self.stat.num += 1
		self.stat.code[u"".join(self.ret)] += 1
		self.stat.dict_code.setdefault(self.src, []).append(u"".join(self.ret))

		if seperator :
			self.ret.append(u'_')
			self.chunks.append(u'_')

		return [self.ret, self.chunks]

	def report (self) :
		print self.stat.__str__()

def main () :

	form_non_tonal = u'abécëiè'
	form_tonal     = u'àbèc.eleh'
	options_obj = options(REMPLACEMENT_INTERDIT = True,SHAPING_TOKEN_IN = True)

	if options_obj.SHAPING_TOKEN_IN :
		print "src (reshaped) : ", reshaping(form_non_tonal)
	else:
		print "src            : ", form_non_tonal
	print "dst            : ", form_tonal

	enc = encoder_tones(options_obj)
	[codes, chunks] = enc.differential_encode (form_non_tonal, form_tonal)

	for chunk, code in zip(chunks, codes) :
		sys.stdout.write(u"{} -> {}\n".format(chunk, code));
	print get_mode_position_table()
	enc.report()

if __name__ == "__main__" : main()
