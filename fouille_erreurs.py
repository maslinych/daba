#coding=utf-8

import re, argparse, sys, codecs
from collections import Counter
from differential_tone_coding import markers_tone

def stat_from_cnt (cnt) :

	tot = sum(cnt.values())
	for k in ['E_c','E_p','E_pc','E_noise','E_silence'] :
		print k,str(round(cnt[k] / float(tot) * 100, 2))+"%"

def rm_deletion (str_in) :

	str_out = ''
	record = True
	for c in str_in :
		if record :
			if c != '-':
				str_out += c
			else :
				record = False
		else :
			if c == '+':
				str_out += c
				record = True

	return str_out


def line2entries (str_in, min_len = 6, max_len = 6) :

	regex = re.compile('[\n\r]')
	str_in = regex.sub('', str_in)
	entries = str_in.strip().split(',')
	if len(entries) < min_len or len(entries) > max_len : entries = None
	return entries

def align(dico, lst1, lst2, position_to_match = -1) :

	if lst2 == [u"NULL"] :
		return dico
	if not lst1 :
		return dico

	for i, x in enumerate(lst1) :
		for j, y in enumerate(lst2) :
			if not dico : cond = True
			else :        cond = (i not in dico.keys()) and (j not in dico.values())
			if cond :
				if position_to_match < 0 :
					dico[i] = j
					break
				elif x[position_to_match] == y[position_to_match]:
					dico[i] = j
					break
	return dico

def make_aligned_result(match,ops1,ops2) :

	dst = []
        for i, x in enumerate(ops1) :
                if i in match.keys() :
                        dst.append(ops2[match[i]])
                else :
                        dst.append('')

	return dst

def stat (str1, str2, cnt, cnt2) :

	# les entrées diviser en operation d'édition
	ops1 = [x for x in str1.split('+') if x]
	ops2 = [x for x in str2.split('+') if x]

	# alignement pas très efficace
	match = dict()
	match = align(match, ops1, ops2, 0)
	match = align(match, ops1, ops2, 1)
	match = align(match, ops1, ops2)
	dst = make_aligned_result(match, ops1, ops2)
	src = ops1

	# stat : op = p,c
	for op, op2 in zip(src, dst) :
		if op[1] not in markers_tone :
			continue
		if not op2 : # silence
			tag = 'silence'
			tag2 = ''
		elif op == op2 : # perfect
			tag = 'good'
			tag2 = op[1]
		elif op[0] == op2[0] : # E_c - E_p
			tag = 'error_only_on_character'
			tag2 = op[1] + u'___' + op2[1]
		elif op[1] == op2[1] : # E_p - E_c
			tag = 'error_only_on_position'
			tag2 = ''
		else : # E_p inter E_c
			tag = 'error_others'
			tag2 = ''

		cnt[tag] += 1
		if tag2 : cnt2[tag2] += 1

	return [cnt,cnt2]

def main(infile) :

	cnt = Counter()
	cnt2 = Counter()
	with codecs.open(infile,'r', encoding='utf-8') as f :
		for line in f:

			cols = line2entries(line)
			if cols :
				token, gold_form, test_form, gold_code, test_code, cmp = cols
				gold_code_segments = gold_code.split()
				test_code_segments = test_code.split()
				for gold_code_segment, test_code_segment in zip(gold_code_segments, test_code_segments) :
					gold_code_segment = rm_deletion(gold_code_segment)
					test_code_segment = rm_deletion(test_code_segment)
					if gold_code_segment != "NULL" and gold_code_segment :
						cnt,cnt2 = stat(gold_code_segment, test_code_segment, cnt,cnt2)
	return  cnt,cnt2

def print_cnt (cnt) :

	tot = sum(cnt.values())
	for k in cnt.keys() :
		print k, str(round(cnt[k] / float(tot) * 100.0, 2))+'%'

if __name__ == "__main__" :

        aparser = argparse.ArgumentParser()
        aparser.add_argument('infile' , help='Input file (.csv)' , default=sys.stdin)
        args = aparser.parse_args()
	cnt,cnt2 = main(args.infile)
	print_cnt(cnt)
	print ""
	print_cnt(cnt2)
