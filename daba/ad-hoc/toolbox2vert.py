#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import argparse
import collections
import codecs
import json
import sys
import os
from itertools import izip_longest
from nltk import toolbox
from xml.sax.saxutils import quoteattr
from daba.ntgloss import Gloss
from daba.formats import WordToken, PlainToken, HtmlWriter
import xml.etree.cElementTree as e


class ShDoc(object):
    def __init__(self):
        self.metadata = []
        self.records = []


class ShToken(collections.namedtuple('ShToken', 'type, word, morphemes')):
    __slots__ = ()

    def as_glosstoken(self, config):
        token = self.word[config.daba['token']]
        if self.type == 'w':
            form = self.word[config.daba['word']]
            morphemes = []
            for m in self.morphemes:
                morphemes.append(self.morph2gloss(m, config.daba['morpheme']))
            if len(morphemes) == 1:
                gt = WordToken([morphemes[0]], token=token)
            else:
                try:
                    ps = filter(lambda s: 'mrph' not in s.ps, morphemes)[0].ps
                except IndexError:
                    ps = ''
                gloss = u'-'.join([m.gloss for m in morphemes])
                g = Gloss(form, ps, gloss, morphemes)
                gt = WordToken([g], token=token)
        elif self.type == 'c':
            gt = PlainToken((self.type, token))
        return gt

    def morph2gloss(self, morph, keys):
        u"convert OrderedDict into Gloss"
        parts = [morph.get(k) for k in keys]
        parts[1] = (parts[1],)
        parts.append((),)
        return Gloss(*parts)


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
        try:
            return self._dict[key]
        except KeyError:
            return ''

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return repr(self._dict)

    def __unicode__(self):
        return str(self._dict)


class Layers(collections.Iterable):
    def __init__(self, tuples):
        self.names = []
        toks = []
        for name, value in tuples:
            self.names.append(name)
            toks.append(value)
        self.tokens = map(lambda v: ShGloss(zip(self.names, v)), izip_longest(*toks, fillvalue=''))

    def __iter__(self):
        return iter(self.tokens)

    def __unicode__(self):
        ' '.join(str(i) for i in self.tokens)

    def __len__(self):
        return len(self.tokens)


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
        # default settings
        self.tc = TokenConverter(self)
        self.macro = {
            'LEMMA': self.tc.lemmatizer,
            'TAG': self.tc.tagger,
            'PARTS': self.tc.derivator
        }
        defaults = u'''
{
    "recstarters": ["id", "ref"],
    "reclabel": "ref",
    "docid": "id",
    "tagfield": "ps",
    "glossfield": "gf",
    "annotlevels": {
        "document": "id",
        "sentence": ["ref", "ft", "fte"],
        "token": "tx",
        "morpheme": ["mb", "ps", "ge"]
        },
    "columns":[
        "tx",
        "LEMMA",
        "TAG",
        "mb",
        "ge",
        "PARTS"
        ],
    "daba": {
        "token": "tx",
        "word": "tx",
        "morpheme": ["mb", "ps", "ge"]
        }
}
'''
        self.set_options(json.loads(defaults))
        # update from config file
        if filename:
            with codecs.open(filename, 'r', encoding='utf-8') as conffile:
                conf = json.load(conffile)
            self.set_options(conf)

    def set_options(self, optdict):
        for key in optdict:
            if key == 'columns':
                value = [self.macro.get(item, item) for item in optdict[key]]
            else:
                value = optdict[key]
            setattr(self, key, value)


class Record(object):
    def __init__(self, fields, config):
        self.metadata = []
        self._tokens = []
        self._morphemes = []
        self.atdoclevel = False
        self.config = config

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
        return re.findall(u'[^ .,:;?!()"“”–‒«»]+|[.,:;?!()"“–‒”«»]+', string)

    def __nonzero__(self):
        return bool(self.metadata) or bool(self._tokens) or bool(self._morphemes)

    def ispunct(self, string):
        return bool(re.match(u'[.,:;?!()"“”–‒«»]+$', string))

    def get_senttext(self):
        tdict = dict(self._tokens)
        return u' '.join(tdict[self.config.daba['token']])

    def get_senttoken(self):
        return PlainToken(('</s>', self.get_senttext()), attrs=dict(self.metadata))

    def itokens(self):
        morphs = collections.deque(self.morphemes)
        npunct = 0
        for tok in self.tokens:
            morphemes = []
            if self.ispunct(tok.base):
                toktype = 'c'
                npunct += 1
                if tok.base == '-':
                    morphemes.append(morphs.popleft())
            else:
                toktype = 'w'
                # only if sentence is glossed
                if self.morphemes:
                    try:
                        morphemes.append(morphs.popleft())
                    except IndexError:
                        try:
                            print(dict(self.metadata)[self.config.docid],)
                        except KeyError:
                            print("UNK",)
                        print("tokens:", len(self.tokens), "punct:", npunct, "morphemes:", len(self.morphemes))

                while morphs and morphs[0].isaffix:
                    morphemes.append(morphs.popleft())
            yield ShToken(**{'type': toktype, 'word': tok, 'morphemes': morphemes})


class ToolboxReader(object):
    def __init__(self, infile, conffile=None, **kwargs):
        self.infile = infile
        self.config = Config(conffile)
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
            if marker in self.config.recstarters:
                out = recdict.items()
                recdict = collections.OrderedDict([(marker, value)])
                yield Record(out, self.config)
            else:
                if marker in recdict:
                    value = recdict[marker].strip() + ' ' + value
                recdict[marker] = value
        out = recdict.items()
        yield Record(out, self.config)

    def get_docs(self):
        out = collections.OrderedDict()
        records = []
        inrec = 0
        docid = ''
        for record in self.irecords():
            if not record:
                continue
            if record.atdoclevel:
                if inrec == 1:
                    out[docid].records = records
                    records = []
                docid = dict(record.metadata)[self.config.docid]
                out[docid] = ShDoc()
                out[docid].metadata = record.metadata
                inrec = 1
            else:
                records.append(record)
        out[docid].records = records
        return out


class BaseFormatter(object):
    def normalize_docpath(self, docid):
        rdict = {' ': '_',
                 '.': '-',
                 '"': '',
                 '&': '_and_',
                 ':': '-'}
        s = docid.strip(' .')
        return reduce(lambda x, y: x.replace(y, rdict[y]), rdict, s)

    def write(self):
        if self.split:
            for docid in self.docs:
                fname = u'.'.join([self.normalize_docpath(docid),
                                   self.extension])
                if self.outdir:
                    fname = os.path.join(self.outdir, fname)
                with codecs.open(fname, 'w', encoding='utf-8') as out:
                    formatted = self.format_doc(self.docs[docid])
                    out.write(formatted)
        else:
            with codecs.open(self.outfile, 'wb', encoding='utf-8') as out:
                for docid in self.docs:
                    formatted = self.format_doc(self.docs[docid])
                    out.write(formatted)


class VertFormatter(BaseFormatter):
    def __init__(self, docs, parser, outfile=None, split=False, outdir=None):
        self.docs = docs
        self.parser = parser
        self.outfile = outfile
        self.split = split
        self.extension = 'vert'
        self.outdir = outdir

    def print_metadata(self, record):
        return u' '.join([u'{0}={1}'.format(k, quoteattr(v)) for k, v in record.metadata])

    def print_token(self, token):
        return self.parser.config.tc.convert(token)

    def format_doc(self, doc):
        vert = []
        vert.append(u'<doc {}>\n'.format(self.print_metadata(doc)))
        for record in doc.records:
            vert.append(u'<s {}>\n'.format(self.print_metadata(record)))
            for token in record.itokens():
                vert.append(u'{}\n'.format(self.print_token(token)))
            vert.append(u'</s>\n')
        vert.append('</doc>\n')
        return u''.join(vert)


class DabaFormatter(BaseFormatter):
    def __init__(self, docs, parser, outfile=None, split=False, outdir=None):
        self.docs = docs
        self.parser = parser
        self.outfile = outfile
        self.split = split
        self.extension = 'sh.html'
        self.outdir = outdir

    def format_doc(self, doc):
        metadata = dict(doc.metadata)
        para = []
        for record in doc.records:
            senttoken = record.get_senttoken()
            sentannot = [t.as_glosstoken(self.parser.config) for t in record.itokens()]
            para.append((senttoken, sentannot))
        ft = HtmlWriter((metadata, [para]))
        return e.tostring(ft.xml, encoding='utf8').decode('utf8')


class FilelistFormatter(BaseFormatter):
    def __init__(self, docs):
        self.docs = docs

    def write(self):
        out = []
        for docid in self.docs:
            out.append(self.normalize_docpath(docid))
        sys.stdout.write(u' '.join(out).encode('utf-8'))
        sys.stdout.write('\n')


def main():
    aparser = argparse.ArgumentParser("Toolbox to vertical format converter.")
    aparser.add_argument('-i', '--infile',
                         help='Input file (toolbox format)')
    aparser.add_argument('-o', '--outfile',
                         help='Output file (vertical format)')
    aparser.add_argument('-d', '--outdir', default=None,
                         help='Output directory')
    aparser.add_argument('-c', '--config',
                         help='Configuration file to use')
    aparser.add_argument('-s', '--split', action='store_true',
                         help='Split output into separate files')
    aparser.add_argument('-f', '--format', choices=['vert', 'daba', 'list'],
                         default='vert', help='Output format')
    args = aparser.parse_args()

    fileparser = ToolboxReader(infile=args.infile, conffile=args.config)
    if args.format == 'vert':
        formatter = VertFormatter(docs=fileparser.get_docs(),
                                  parser=fileparser, outfile=args.outfile, split=args.split, outdir=args.outdir)
    elif args.format == 'daba':
        formatter = DabaFormatter(docs=fileparser.get_docs(),
                                  parser=fileparser, outfile=args.outfile, split=args.split, outdir=args.outdir)
    elif args.format == 'list':
        formatter = FilelistFormatter(docs=fileparser.get_docs())
    formatter.write()


if __name__ == '__main__':
    main()
