#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import sys
import argparse
import collections
from itertools import izip_longest
from nltk import toolbox

class Config(object):
    def __init__(self, filename=None):
        if not filename:
            # default settings
            self.recstarter = 'ref'
            self.annotlevels = {
                    'document': ['id'],
                    'sentence': ['ref', 'txor', 'ft', 'ftor', 'fte'],
                    'token': ['tx'],
                    'morpheme': ['mb', 'ps', 'ge', 'gr'] 
                    }
        else:
            #FIXME parse config file
            pass
        self.fieldtypes = dict((v,k) for k, l in self.annotlevels.iteritems() for v in l)


class Layers(collections.Iterable):
    def __init__(self, tuples):
        self.names = []
        toks = []
        for name, value in tuples:
            self.names.append(name)
            toks.append(value)
        self.tokens = map(lambda v: zip(self.names,v), izip_longest(*toks, fillvalue=''))

    def __iter__(self):
        return iter(self.tokens)
       

class Record(object):
    def __init__(self, fields, config):
        self.metadata = []
        self._tokens = []
        self._morphemes = []

        for marker, value in fields:
            if marker in config.annotlevels['sentence']:
                self.metadata.append((marker, value))
            elif marker in config.annotlevels['token']:
                self._tokens.append((marker, self._tokenize(value)))
            elif marker in config.annotlevels['morpheme']:
                self._morphemes.append((marker, value.split()))

        self.tokens = Layers(self._tokens)
        self.morphemes = Layers(self._morphemes)

    def _tokenize(self, string):
        return re.findall('[^ .,:;?!()"“”]+|[.,:;?!()"“”]+', string)

    def ispunct(self, string):
        return bool(re.match('[.,:;?!()"“”]+$', string))

    def itokens(self):
        morphs = collections.deque(self.morphemes)
        for tok in self.tokens:
            morphemes = []
            if self.ispunct(tok[0][1]):
                toktype = 'c'
                if tok[0][1] == '-':
                    morphemes.append(morphs.popleft())
            else:
                toktype = 'w'
                try:
                    morphemes.append(morphs.popleft())
                except IndexError:
                    print 'TTT', tok
                    print 'ispunct', self.ispunct(tok[0][1])

                while morphs and morphs[0][0][1].startswith('-') and len(morphs[0][0][1]) > 1:
                        morphemes.append(morphs.popleft())
            yield {'type': toktype, 'token': tok, 'morphemes': morphemes}


class TokenConverter(object):
    def __init__(self, token):
        pass
        

class Parser(object):
    def __init__(self, infile, config=Config(), **kwargs):
        self.infile = infile
        self.config = config
        self.kwargs = kwargs
        self.f = toolbox.StandardFormat()
        self.f.open(infile)

    def __del__(self):
        self.f.close()

    def irecords(self):
        recdict = collections.OrderedDict()
        self.fields = self.f.fields(**self.kwargs)
        for marker, value in self.fields:
            if marker == self.config.recstarter:
                out = recdict.items()
                recdict = collections.OrderedDict([(marker, value)])
                yield Record(out, self.config)
            else:
                if marker in recdict:
                    value = recdict[marker].strip() + ' ' + value
                recdict[marker] = value


class VertFormatter(object):
    def __init__(self, record):
        pass

    def _escape_attribute(self, string):
        #FIXME write escaping function
        pass
 
    def as_vertical(self):
        out = []
        metastr = u' '.join([u'{0}="{1}"'.format(k,v) for k,v in self.metadata])
        out.append('<s' + metastr + '>')
        for tok in self.itokens:
            tokstr = u'\t'.join(self.convert_token(tok))
        out.append('</s>')

def main():
    from pprint import pprint
    aparser = argparse.ArgumentParser("Toolbox to vertical format converter.")
    aparser.add_argument('-i', '--infile', help='Input file (toolbox format).')
    aparser.add_argument('-o', '--outfile', help='Output file (vertical format).')
    args = aparser.parse_args()

    fileparser = Parser(args.infile)
    for record in fileparser.irecords():
        print 'TOKS', record._tokens
        print 'MORPHS', record._morphemes
        pprint([i for i in record.morphemes])
        for token in record.itokens():
            pprint(token)

if __name__ == '__main__':
    main()
