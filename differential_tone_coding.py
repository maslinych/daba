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
token_seperator = u'_'
code_seperator = u'_'
mode_indicators = u'-+='
mode_names   = [u"delete",u"insert",u"replace"]
markers_to_be_ignored = u"[]. ̀’'-" + code_seperator

def repr (c, null = "") :
	if not c : return null
	else : return rm_sep(c)

def rm_sep(str_in, seprator_in = code_seperator, replacing = u''):
	try :
		return str_in.replace(seprator_in, u"")
	except:
		try :
			return str_in.decode('utf-8').replace(seprator_in, replacing).encode('utf-8')
		except :
			try :
				return str_in.encode('utf-8').replace(seprator_in, replacing).decode('utf-8')
			except :
				raise

# Turning Options
class options() :
	def __init__(self, \
		REMPLACEMENT_INTERDIT          = False,\
		DECOMPOSE_OPS_FOR_TONES        = False,\
		ONLY_TONE_PREDICTION           = False,\
		SHAPING_TOKEN_IN               = False) :
		self.REMPLACEMENT_INTERDIT = REMPLACEMENT_INTERDIT
		self.DECOMPOSE_OPS_FOR_TONES = DECOMPOSE_OPS_FOR_TONES
		self.ONLY_TONE_PREDICTION = ONLY_TONE_PREDICTION
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
		token = u"".join(c for c in token if unicodedata.category(c) != 'Mn' and c not in markers_to_be_ignored)
	else :
		token = u"".join(c for c in token if c not in markers_to_be_ignored)

	return token.lower()

def mode_position_encoder (token, position, mode_id, chunks, offset = 0, code_seperator_in = code_seperator) :

	mode_indicator = mode_indicators[mode_id]
	caracter_position_in_token = position + offset
	caracter_position_in_chunk = 0
	chunk_id = 0
	if mode_id == mode_names.index('insert') :
		chunk_position_limit_offset = 1
	else :
		chunk_position_limit_offset = 0
	chunk_position_limit = len(chunks[chunk_id]) + chunk_position_limit_offset

	for i in range(len(token) + 1):
		if i == caracter_position_in_token:
			mp_code = mode_indicator + code_seperator_in + str(caracter_position_in_chunk)
			return [mp_code, chunk_id]

		caracter_position_in_chunk += 1
		if caracter_position_in_chunk == chunk_position_limit :
			chunk_id += 1
			caracter_position_in_chunk = chunk_position_limit_offset
			chunk_position_limit = len(chunks[chunk_id]) + chunk_position_limit_offset

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


def sprint_cnt(cnt, prefix = "", num = -1, min = -1) :

	lst = cnt.most_common()
	if num > 0 :
		try :
			lst = lst[:num]
		except IndexError :
			pass
	if min > 0 :
		lst = [element for element in lst if element[1] >= min]

	try :
		return u"".join([prefix + ' '  + itm[0].encode('utf-8') + u' : ' + str(itm[1]).encode('utf-8') + u'\n' for itm in lst if itm])
	except :
		return u"".join([prefix + ' ' + itm[0] + u' : ' + str(itm[1]) + u'\n' for itm in lst if itm])

class statistique () :
	def __init__(self, options) :
		self.form_non_tonal = Counter()
		self.form_tonal     = Counter()
		self.code           = Counter()
		self.segment_code   = Counter()
		self.dict_code      = defaultdict()
		self.dict_form_tonal= defaultdict()
		self.num   = 0
		self.cnt_ops = 0
		self.mode = Counter()
		self.options = options
		self.src_replace = Counter()
		self.dst_replace = Counter()
		self.src_delete = Counter()
		self.dst_insert = Counter()

	def __str__(self) :

		ret  = u""
		ret += u"Sur un ensemble de corpus de {} mot(s)\n".format(str(self.num))
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
		ret += u"\nConfigurations\n"
		ret += u"\tREMPLACEMENT_INTERDIT          = {}\n".format(self.options.REMPLACEMENT_INTERDIT)
		ret += u"\tDECOMPOSE_OPS_FOR_TONES        = {}\n".format(self.options.DECOMPOSE_OPS_FOR_TONES)
		ret += u"\tONLY_TONE_PREDICTION           = {}\n".format(self.options.ONLY_TONE_PREDICTION)
		ret += u"\tSHAPING_TOKEN_IN               = {}\n".format(self.options.SHAPING_TOKEN_IN)

		ret += u"Distribution sur : \n"
		ret += u"\tLes opérations d'édition : \n" + sprint_cnt(self.mode, u"\t\t",-1,20)
		ret += u"\tL'ensemble des codes par syllabe : \n" + sprint_cnt(self.code, u"\t\t",-1,20)
		ret += u"\tL'ensemble des codes par leur segment atomique : \n" + sprint_cnt(self.segment_code, u"\t\t",-1,20)
		ret += u"\tL'ensemble des caractères supprimés : \n" + sprint_cnt(self.src_delete, u"\t\t",-1,20)
		ret += u"\tL'ensemble des caractères inserés : \n" + sprint_cnt(self.dst_insert, u"\t\t",-1,20)
		ret += u"\tL'ensemble des caractères replacés : \n" + sprint_cnt(self.src_replace, u"\t\t",-1,20)
		ret += u"\tL'ensemble des caractères replaçants : \n" + sprint_cnt(self.dst_replace, u"\t\t",-1,20)
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
		mode_id = mode_names.index("delete")
		[mp_code, chunk_id] = mode_position_encoder(self.src,self.p_src, mode_id, self.chunks)
		segment = mp_code + code_seperator
		caracter_src = self.src[self.p_src]
		segment += caracter_src + code_seperator
		self.ret[chunk_id] += segment

		self.stat.cnt_ops += 1
		self.stat.mode["delete"] += 1
		self.stat.src_delete[caracter_src] += 1
		self.stat.segment_code[repr(segment)] += 1

	def insert(self) :
		mode_id = mode_names.index("insert")
		[mp_code, chunk_id] = mode_position_encoder(self.src,self.p_src, mode_id, self.chunks)
		segment = mp_code + code_seperator
		caracter_dst = self.dst[self.p_dst]
		segment += caracter_dst + code_seperator
		self.ret[chunk_id] += segment

		self.stat.cnt_ops += 1
		self.stat.mode["insert"] += 1
		self.stat.dst_insert[caracter_dst] += 1
		self.stat.segment_code[repr(segment)] += 1

	def replace(self) :
		mode_id = mode_names.index("replace")
		[mp_code, chunk_id] = mode_position_encoder(self.src,self.p_src, mode_id, self.chunks)
		segment = mp_code + code_seperator
		caracter_src = self.src[self.p_src]
		caracter_dst = self.dst[self.p_dst]
		segment += caracter_dst + code_seperator
		self.ret[chunk_id] += segment

		self.stat.cnt_ops += 1
		self.stat.mode["replace"] += 1
		self.stat.src_replace[caracter_src] += 1
		self.stat.dst_replace[caracter_dst] += 1
		self.stat.segment_code[repr(segment)] += 1

	def differential_encode (self, form_non_tonal, form_tonal, seperator = True) :

		self.p_src = -1
		self.p_dst = -1

		if self.options.SHAPING_TOKEN_IN :
			self.src = reshaping(form_non_tonal, True)
		else:
			self.src = reshaping(form_non_tonal, False)

		if not self.src :
			if seperator:
				return [u"", [token_seperator]]
			else :
				return [u"", []]

		self.chunks = chunking(self.src)
		self.ret = [u"" for i in range(len(self.chunks))]

		self.dst = reshaping(form_tonal, False)
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
				      (self.options.ONLY_TONE_PREDICTION and (self.dst[self.p_dst] in markers_tone)) :
					self.insert()

			else : # mode == "replace"
				if not self.options.ONLY_TONE_PREDICTION or \
				      (self.options.ONLY_TONE_PREDICTION and (self.dst[self.p_dst] in markers_tone)) :

					if self.options.REMPLACEMENT_INTERDIT or \
					   (self.dst[self.p_dst] in markers_tone and self.options.DECOMPOSE_OPS_FOR_TONES) :

						self.delete()
						self.insert()
					else :
						self.replace()

		tmp = []
                for ret2 in self.ret :
			try :
                        	if ret2[-1] == code_seperator :
                                	ret2 = ret2[:-1]
			except IndexError:
				pass
                        tmp.append(ret2)
                self.ret = tmp

		self.stat.num += 1
		repr_code = repr(u"".join(self.ret))
		self.stat.code[repr_code] += 1
		self.stat.dict_code.setdefault(self.src, []).append(repr_code)

		if seperator :
			self.ret.append(u'')
			self.chunks.append(token_seperator)

		return [self.ret, self.chunks]

	def report (self) :
		print self.stat.__str__()

def differential_decode (chunk, code) :

	chunk = u"".join([c for c in chunk if c not in markers_to_be_ignored])

	if len(code.strip()) == 0 : return chunk

	code_segments = code.split(code_seperator)
	if len(code_segments) % 3 != 0 : print (code_segments) ; print ("input code incorrect !"); exit(1)

	p_offset = 0
	for i in range(0,len(code_segments),3) :
		try :
			#print i, len(chunk)
			m, p, c = code_segments[i:i+3]
		except :
			print (u"Bug in differential_decode : {}".format(code))
			exit(1)

		p_eff = int(p) + p_offset
		if m == mode_indicators[mode_names.index('delete')] :
			try : l = chunk[: p_eff]
			except IndexError : l = ''
			try : r = chunk[p_eff + 1 :]
			except IndexError : r = ''
			chunk = l + r
			p_offset -= 1
		elif m == mode_indicators[mode_names.index('insert')] :
			try : l = chunk[: p_eff]
			except IndexError : l = ''
			try : r = chunk[p_eff  :]
			except IndexError : r = ''
			chunk = l + c + r
			p_offset += 1
		else : # 'replace'
			try : l = chunk[: p_eff ]
			except IndexError : l = ''
			try : r = chunk[p_eff + 1 :]
			except IndexError : r = ''
			chunk = l + c + r

	return chunk

def main () :

	form_non_tonal = u'éce'
	form_tonal     = u'àcé'
	options_obj = options()

	print "src : ", reshaping(form_non_tonal, False)
	print "dst : ", reshaping(form_tonal    , False)

	enc = encoder_tones(options_obj)
	[codes, chunks] = enc.differential_encode (form_non_tonal, form_tonal)
	form_tonal_reproduit = repr(''.join([differential_decode(chunk, code) for code,chunk in zip(codes,chunks)]))

	print form_tonal_reproduit

	if unicodedata.normalize('NFC', form_tonal_reproduit) == \
	   unicodedata.normalize('NFC', form_tonal) :
		print "Oui, le codage marche !"
	else:
		print "Héhé, un problème de codage !"
		print form_tonal,len(form_tonal)
		print form_tonal_reproduit,len(form_tonal)
	for chunk, code in zip(chunks, codes) : sys.stdout.write(u"'{}' - '{}' -> '{}'\n".format(differential_decode(chunk, code), chunk, repr(code)));
	enc.report()


if __name__ == "__main__" : main()
