#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import sys
import argparse
import collections
from itertools import izip_longest
from nltk import toolbox

ShToken = collections.namedtuple('ShToken', 'type, word, morphemes')

class ShGloss(collections.Mapping):
    def __init__(self, tuples):
        self._dict = collections.OrderedDict()
        self.base = None
        self.isaffix = False
        for k, v in tuples:
            if v.startswith('-') and len(v) > 1:
                if self.base is None:
                    self.isaffix = True
                v = v[1:]
            if self.base is None:
                self.base = v
            self._dict[k] = v

    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return repr(self._dict)


class Layers(collections.Iterable):
    def __init__(self, tuples):
        self.names = []
        toks = []
        for name, value in tuples:
            self.names.append(name)
            toks.append(value)
        self.tokens = map(lambda v: ShGloss(zip(self.names,v)), izip_longest(*toks, fillvalue=''))

    def __iter__(self):
        return iter(self.tokens)


class TokenConverter(object):
    def __init__(self, config):
        self.config = config
        
    def isgrammar(self, gloss):
        return bool(re.match('[A-Z0-9.]+$', gloss[self.config.glossfield]))

    def gettag(self, gloss):
        try:
            return gloss[self.config.tagfield]
        except (KeyError):
            return ''

    def getgloss(self, gloss):
        try:
            return gloss[self.config.glossfield]
        except (KeyError):
            return ''

    def lemmatizer(self, token):
        if token.type == 'w' and token.morphemes:
            return token.morphemes[0].base
        else:
            return token.word.base

    def tagger(self, token):
        tags = []
        if token.type == 'c':
            return 'c'
        elif token.type == 'w':
            if token.morphemes:
                tags.append(self.gettag(token.morphemes[0]))
                for m in token.morphemes[1:]:
                    if self.isgrammar(m):
                        tags.append(self.getgloss(m))
        return u'|'.join(tags)

    def derivator(self, token):
        parts = []
        if len(token.morphemes) > 1:
            for m in token.morphemes[1:]:
                if not self.isgrammar(m):
                    parts.append(m.base)
        return u'|'.join(parts)

    def convert(self, token):
        fields = []
        for coltype in self.config.columns:
            if isinstance(coltype, basestring):
                if coltype in self.config.annotlevels['token']:
                    fields.append(token.word[coltype])
                elif coltype in self.config.annotlevels['morpheme']:
                    if token.morphemes:
                        fields.append('-'.join([m[coltype] for m in token.morphemes]))
                    else:
                        fields.append(token.word.base)
            else:
                fields.append(coltype(token))
        return u'\t'.join(fields)


class Config(object):
    def __init__(self, filename=None):
        if not filename:
            # default settings
            self.tc = TokenConverter(self)
            self.recstarter = 'ref'
            self.tagfield = 'ps'
            self.glossfield = 'ge'
            self.annotlevels = {
                    'document': ['id'],
                    'sentence': ['ref', 'txor', 'ft', 'ftor', 'fte'],
                    'token': ['tx'],
                    'morpheme': ['mb', 'ps', 'ge', 'gr'] 
                    }
            self.columns = [
                    # word
                    'tx',
                    # lemma
                    self.tc.lemmatizer,
                    # tag
                    self.tc.tagger,
                    # form
                    'mb',
                    # gloss
                    'ge',
                    # rugloss
                    'gr',
                    # parts
                    self.tc.derivator
                    ]
        else:
            #FIXME parse config file
            pass
      

class Record(object):
    def __init__(self, fields, config):
        self.metadata = []
        self._tokens = []
        self._morphemes = []
        self.atdoclevel = False

        for marker, value in fields:
            marker = marker.decode('utf-8')
            value = value.decode('utf-8')
            if marker in config.annotlevels['sentence']:
                self.metadata.append((marker, value))
            elif marker in config.annotlevels['token']:
                self._tokens.append((marker, self._tokenize(value)))
            elif marker in config.annotlevels['morpheme']:
                self._morphemes.append((marker, value.split()))
            elif marker in config.annotlevels['document']:
                self.metadata.append((marker, value))
                self.atdoclevel = True

        self.tokens = Layers(self._tokens)
        self.morphemes = Layers(self._morphemes)

    def _tokenize(self, string):
        return re.findall(u'[^ .,:;?!()"“”]+|[.,:;?!()"“”]+', string)

    def ispunct(self, string):
        return bool(re.match(u'[.,:;?!()"“”]+$', string))

    def itokens(self):
        morphs = collections.deque(self.morphemes)
        for tok in self.tokens:
            morphemes = []
            if self.ispunct(tok.base):
                toktype = 'c'
                if tok.base == '-':
                    morphemes.append(morphs.popleft())
            else:
                toktype = 'w'
                try:
                    morphemes.append(morphs.popleft())
                except IndexError:
                    print 'TTT', self.tokens

                while morphs and morphs[0].isaffix:
                        morphemes.append(morphs.popleft())
            yield ShToken(**{'type': toktype, 'word': tok, 'morphemes': morphemes})



class ToolboxReader(object):
    def __init__(self, infile, config=Config(), **kwargs):
        self.infile = infile
        self.config = config
        self.kwargs = kwargs
        self.metadata = collections.OrderedDict()
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
    def __init__(self, parser, outfile):
        self.parser = parser
        self.outfile = outfile

    def _escape_attribute(self, string):
        #FIXME write escaping function
        pass
 
    def print_metadata(self, record):
        return u' '.join([u'{0}="{1}"'.format(k,v) for k,v in record.metadata])

    def print_token(self, token):
        return self.parser.config.tc.convert(token)

    def write(self):
        with open(self.outfile, 'wb') as out:
            nrec = 0
            out.write('<doc'.encode('utf-8'))
            for record in self.parser.irecords():
                if record.atdoclevel:
                    if nrec == 0:
                        out.write(u' {}>\n'.format(self.print_metadata(record)).encode('utf-8'))
                        nrec = 1
                else:
                    if nrec == 0:
                        out.write('>\n'.encode('utf-8'))
                    else:
                        out.write(u'<s {}>\n'.format(self.print_metadata(record)).encode('utf-8'))
                        for token in record.itokens():
                            out.write(u'{}\n'.format(self.print_token(token)).encode('utf-8'))
                        out.write(u'</s>\n'.encode('utf-8'))
            out.write('</doc>\n'.encode('utf-8'))


def main():
    from pprint import pprint
    aparser = argparse.ArgumentParser("Toolbox to vertical format converter.")
    aparser.add_argument('-i', '--infile', help='Input file (toolbox format).')
    aparser.add_argument('-o', '--outfile', help='Output file (vertical format).')
    args = aparser.parse_args()

    fileparser = ToolboxReader(args.infile)
    formatter = VertFormatter(fileparser, args.outfile)
    formatter.write()

if __name__ == '__main__':
    main()
