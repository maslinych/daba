#! /bin/sh python
#-*- coding: utf-8 -*
import sys
import unicodedata
import collections
import argparse
import re
from os import listdir
from os.path import isfile, join

# Combining Diacritical Marks Unicode block (including
# the accents respresenting tonalisations in bambara)
# http://www.fileformat.info/info/unicode/block/combining_diacritical_marks/utf8test.htm
# U+0x300 - U+0x36f
listMarker = range(0x300, 0x36f + 1)

if __name__ == "__main__" :

	# paramètres
	regex_filename = ".*non-tonal.vert$"
	markerCnt = collections.Counter()
	# listStrang = [0x0323, 0x030a, 0x030c, 0x030f]
	token_id = 0
	tonal_id = 6

	# ui
	parser = argparse.ArgumentParser(description=\
		'The tone will be analyzed and extracted for each word \
		(from each corpus of the user-specified directory)\
		 using the accent marks defined by the UTF-8 encoding standard. \
		Moreover, a statistic on the distributions \
		in occurrence of accents markers (including those of tone) \
		will be displayed at the end of execution.')
	parser.add_argument('path', action="store")
	args = parser.parse_args()
	mypath = args.path
	onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]

	# principale
	for filename in onlyfiles :
		if re.match(regex_filename, filename) :
			with open(mypath + filename, 'r') as file :
				for line in file :

					try :
						token = line.split('\t')[token_id]
						tonal = line.split('\t')[tonal_id].decode('utf-8')
						len_token = len(token)
						len_tonal = len(tonal)
						i_offset = 0
						if len_token <> len_tonal :
							sys.stdout.write(tonal + " : ")
							for i, c in enumerate(tonal) :
								ucode_c = ord(c)
								if ucode_c in listMarker :
									i_offset += 1
									markerCnt[unichr(ucode_c)] += 1
									sys.stdout.write("{}@{} " . format(hex(ucode_c), i - i_offset))

							print ""

					except IndexError :
						pass
	# bilan
	print "\nThe occurrence of tone markers on the corpus set whose folder path is specified by the user.\n"
	for mark in markerCnt.keys() :
		print " " + mark, " [{}]:".format(mark.encode('raw_unicode_escape')), markerCnt[mark]
