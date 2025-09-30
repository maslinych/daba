#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2010—2019  Kirill Maslinsky <kirill@altlinux.org>
#
# This file is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#

import os
import argparse
import sys
import pickle
import funcparserlib.lexer
import pkg_resources

import daba.formats
import daba.newmorph
import daba.grammar
from daba.ntgloss import Gloss, emptyGloss
from daba.plugins import OrthographyConverter
from daba.plugins.tokenizer import TokenizerData
from daba.orthography import tones_match, detone

import re  # JJM used in removing tones

class Tokenizer(object):
    def __init__(self):
        self._data = TokenizerData()
        self.methods = self._data.methods
        self.specs = self._data.get("default")

    def use_method(self, method):
        self.specs = self._data.get(method)
        
    def tokenize(self, string):
        'unicode -> Sequence(Token)'
        tok = funcparserlib.lexer.make_tokenizer(self.specs)
        r = tok(string)
        # print("TKS", [t for t in r])
        return r

    def split_sentences(self, toklist):
        senttoks = []
        bordertypes = ['SentPunct', 'Par']
        border = False
        for n, tok in enumerate(toklist):
            senttoks.append(tok)
            if tok.type in bordertypes:
                border = True
            elif tok.type not in bordertypes and border:
                border = False
                yield senttoks[:-1]
                senttoks = [tok]
            else:
                border = False
        else:
            yield senttoks


class ChainDict(object):
    def __init__(self, *maps):
        self._maps = dict((dic.hash, dic) for dic in maps)

    @property
    def ids(self):
        return self._maps.keys()

    @property
    def dictlist(self):
        return self._maps.values()

    def __len__(self):
        return sum([len(dic) for dic in self.dictlist])

    def __iter__(self):
        for dic in self.dictlist:
            for key in dic:
                yield key

    def __contains__(self, key):
        for dic in self.dictlist:
            if key in dic:
                return True
        return False

    def __getitem__(self, key):
        result = []
        for mapping in self.dictlist:
            try:
                result.extend(mapping[key])
            except KeyError:
                pass
        if result:
            return result
        else:
            raise KeyError(key)

    def iter_prefixes(self, key):
        result = set()
        for dic in self.dictlist:
            for prefix in dic.iter_prefixes(key):
                result.add(prefix)
        return result

    def items(self):
        result = []
        keysseen = []
        for mapping in self.dictlist:
            for key in mapping:
                if key not in keysseen:
                    for lookup in self.dictlist:
                        try:
                            result.extend(lookup[key])
                        except (KeyError):
                            pass
                    yield (key, result)
                    keysseen.append(key)
                    result = []

    def get_dict(self, sha):
        return self._maps[sha]

    def add(self, dic):
        self._maps[dic.hash] = dic

    def remove(self, sha):
        del self._maps[sha]

    def replace(self, sha, dic):
        self._maps[sha] = dic


class DictLoader(object):
    """ Object holding info about dictionaries state.
    """
    def __init__(self, runtimedir='./run', verbose=False):
        self.runtimedir = runtimedir
        self.dictionary = ChainDict()
        self.verbose = verbose
        if not os.path.exists(self.runtimedir):
            os.mkdir(self.runtimedir)
        else:
            for f in os.listdir(self.runtimedir):
                name, ext = os.path.splitext(f)
                if ext in ['.bdi']:
                    with open(os.path.join(self.runtimedir, f), 'rb') as bdi:
                        dic = pickle.load(bdi)
                        assert isinstance(dic, daba.formats.DabaDict)
                        self.load(dic)

    def filepath(self, dic):
        return os.path.join(self.runtimedir, os.path.extsep.join(['-'.join([dic.lang, dic.name, dic.hash]), 'bdi']))

    def load(self, dic):
        if self.verbose:
            sys.stderr.write(u'LOADED DICT {}\n'.format(dic))
        self.dictionary.add(dic)

    def addfile(self, dictfile):
        dic = daba.formats.DictReader(dictfile).get()
        if not dic.hash in self.dictionary.ids:
            self.add(dic)
            return dic.hash

    def add(self, dic):
        for d in self.dictionary.dictlist:
            if (dic.lang, dic.name) == (d.lang, d.name):
                if not (dic.ver, dic.hash) == (d.ver, d.hash):
                    break
                else:
                    # don't save dic if we already have identical one
                    return (dic.lang, dic.name)
        else:
            self.save(dic)
            return dic.hash
        self.remove(d.hash)
        self.save(dic)
        return dic.hash

    def remove(self, dicid):
        for d in self.dictionary.dictlist:
            if d.hash == dicid:
                dic = d
                break
        if self.verbose:
            sys.stderr.write(u'REMOVED DICT {}\n'.format(dic))
        self.dictionary.remove(dic.hash)
        os.unlink(self.filepath(dic))

    def save(self, dic):
        if self.verbose:
            sys.stderr.write(u'DICT saved {}\n'.format(dic))
        self.load(dic)
        with open(self.filepath(dic), 'wb') as o:
            pickle.dump(dic, o)


class GrammarLoader(object):
    def __init__(self, runtimedir="./run"):
        self.runtimedir = runtimedir
        self.gramlist = []
        self.grammar = None
        for f in os.listdir(self.runtimedir):
            name, ext = os.path.splitext(f)
            if ext in ['.bgr']:
                try:
                    with open(os.path.join(self.runtimedir, f), 'rb') as gram:
                        g = pickle.load(gram)
                    assert isinstance(g, daba.grammar.Grammar)
                    self.gramlist = [name]
                    self.grammar = g
                except (pickle.UnpicklingError, ImportError, AssertionError):
                    #FIXME: raise an exception with error message
                    print("Invalid binary grammar file:", f)
    
    def load(self, gramfile):
        self.grammar = daba.grammar.Grammar(gramfile)
        self.gramlist = [os.path.basename(gramfile)]
        # take basename of the gramfile as a 
        for f in os.listdir(self.runtimedir):
            name, ext= os.path.splitext(f)
            if ext in ['.bgr']:
                os.unlink(os.path.join(self.runtimedir, f))
        with open(os.path.join(self.runtimedir, os.path.extsep.join([os.path.basename(gramfile), 'bgr'])), 'wb') as o:
            pickle.dump(self.grammar, o)


class Processor(object):
    def __init__(self, dictloader=None, grammarloader=None,
                 tokenizer=None, converters=None, detone=False, nolemmas=False,
                 normalize_orthography=False, has_sentences=False):
        if converters:
            plugins = OrthographyConverter.get_plugins()
            self.converters = [plugins[c] for c in converters]
        else:
            self.converters = ()
        self.tokenizer = tokenizer
        self.detone = detone
        self.normalize_orthography = normalize_orthography
        if has_sentences:
            def sent_splitter(para):
                for s in para:
                    st = list(self.tokenizer.tokenize(s))
                    yield st
        else:
            def sent_splitter(para):
                return self.tokenizer.split_sentences(self.tokenizer.tokenize(para))
        self.sentence_splitter = sent_splitter
        if nolemmas:
            class Noparser(object):
                def lemmatize(self, wform):
                    return ('-1', [emptyGloss._replace(form=wform)])
            self.parser = Noparser()
        else:
            self.dictloader = dictloader
            self.grammar = grammarloader.grammar
            self.parser = daba.newmorph.Parser(self.dictloader.dictionary,
                                          self.grammar, detone=self.detone)

    def get_case(self, string):
        string = detone(string)
        if string.isupper():
            case = unicode.upper
        elif string.istitle():
            case = lambda s: u''.join([s[0].upper(), s[1:]])
        else:
            case = unicode.lower
        return case

    def convert_orthography(self, word):
        # print("GOT", word,)
        wlist = [word]
        for plugin in self.converters:
            converted = []
            for w in wlist:
                # print("w:'"+w+"'") # if next line starts with " we have here '\n"' ???
                # if '\n' in w : w=w.replace('\n','')
                # this should NEVER happen given the definition of 'Par' in tokenizer.py!!!
                for result in plugin.convert(w):
                    converted.append(result)
            wlist = converted
        # print("->", u'/'.join(wlist))
        return wlist or [word]
    
    def filter_parsed(self, results, forms):
        stage = max([str(c[0]) for c in results])
        filtered = []
        for r in filter(lambda s: str(s[0]) >= '0', results):
            filtered.extend(r[1])
        if not filtered:
            filtered = [g for glosslist in list(zip(*results))[1] for g in glosslist]
        filtered = list(filter(lambda g: any(tones_match(s, g.form) for s in forms), filtered))
        if not filtered:
            filtered = [emptyGloss._replace(form=w) for w in forms]
        return stage, filtered

    def parse(self, txt):

        def iscapitalized(s):
            if len(s) ==1 : return s.isupper()
            else: return (s[0].isupper() and s[1:].islower())

        self.parsed = []
        for para in txt:
            par = []
            for sent in self.sentence_splitter(para):
                sttoken = daba.formats.PlainToken(('</s>', ''.join(t.value for t in sent)))
                st = (sttoken, [])
                par.append(st)
                annot = st[1]
                wordindex=0
                # print("sent:",sent)
                for token in sent:
                    if token.type in ['Comment', 'Tag']:
                        annot.append(daba.formats.PlainToken((token.type, token.value)))
                    elif token.type in ['Punct', 'SentPunct', 'Nonword']:
                        # annot.append(daba.formats.PlainToken(('c', token.value)))
                        if self.converters:
                            # print("token value:",token.value)
                            ctoken = self.convert_orthography(token.value)[0]
                        else:
                            ctoken = token.value
                        annot.append(daba.formats.PlainToken(('c', ctoken)))
                        # print('PUNCT token.value=',token.value)
                        if token.value in [":","«",'"','“',"-","("] :
                            wordindex=0  # need to reset, next word in Capital like at start of sentence - for instance after : or «
                            # print("(in) wordindex=",wordindex,"token.value=",token.value) 
                            
                    elif token.type in ['Cardinal']:
                        gloss = Gloss(token.value, ('num',), 'CARDINAL', ())
                        annot.append(daba.formats.WordToken([gloss], token.value, 'tokenizer'))
                    elif token.type in ['Word']:
                        wordindex+=1
                        if self.converters:
                            wlist = self.convert_orthography(token.value)
                            # print("token.value, wlist", token.value, wlist)
                            converts = []
                            for w in filter(None, wlist):
                                converts.append(
                                    #self.parser.lemmatize(w.lower())
                                    self.parser.lemmatize(w)
                                )
                            try:
                                stage, glosslist = self.filter_parsed(converts, list(filter(None, wlist)))
                            except ValueError:
                                print("WARNING: invalid orthographic conversion result, skippig token:", token.type, token.value, converts)
                        else:
                            #stage, glosslist = self.parser.lemmatize(token.value.lower())
                            stage, glosslist = self.parser.lemmatize(token.value)
                        # but that's not enough:
                        # if stage, glosslist looks like: (-1, [Gloss(form='hawa', ps=(), gloss='', morphemes=())])
                        # we need to try again : if 1st letter is in lower case, try uppercasing it
                        # else if it is in uppercase, try lowercasing it.

                        # for now restricted to results with glosslist limited to one
                        # it would be nice to also tackle longer glosslist with emply morphemes gloss,
                        # where only derivation morphemes are identifiable, e.g. :
                        # propername Keyita, distracted by possible suffix -ta
                        # [Gloss(form='keyita', ps=(), gloss='', morphemes=()), Gloss(form='keyita', ps=('ptcp',), gloss='', morphemes=(Gloss(form='keyi', ps=('v',), gloss='', morphemes=()), Gloss(form='ta', ps=('mrph',), gloss='PTCP.POT', morphemes=())))]
                        # propername Mayiga:, distracted by possible prefix ma-
                        # [Gloss(form='mayiga', ps=(), gloss='', morphemes=()), Gloss(form='mayiga', ps=('v',), gloss='', morphemes=(Gloss(form='mà', ps=('mrph',), gloss='SUPER', morphemes=()), Gloss(form='yiga', ps=('v',), gloss='', morphemes=())))]

                        if len(glosslist)==1 or glosslist[0].gloss=="":
                            gloss=glosslist[0]
                            if (    len(gloss.ps)==0 and gloss.gloss=="") \
                                or (len(gloss.ps)==1 and gloss.ps[0]=="") \
                                or (len(gloss.ps)==1 and gloss.ps[0]=="n.prop") :  
                                #Last test
                                #1) n.prop:NOM is only the default for capitalized token (see bamana.gram.txt)
                                #                  but I removed this rtestriction: and gloss.gloss=="NOM" because:
                                #2) other proper names are inherently misleading and should be presented with alternative lowercase solution
                                # like Sira (also sira: road, path) or Misi (also misi: cow) and many more
                                # not doing so produces ridiculous solutions - JJM 07/02/2025

                                # 01/04/2025 traiter des cas comme
                                # cikɛ-bolofarakuntigi:n: [cikɛ-bolofarakun:n: tìgi:n:maître]
                                # en éliminant le ou les -

                                trythis=""

                                if self.converters:
                                    wlist = self.convert_orthography(token.value)
                                    trythis=wlist[0]

                                    if "-" in trythis: 
                                        wlist.append(trythis.replace("-",""))

                                    if trythis.islower():
                                        converts = []
                                        for w in filter(None, wlist):
                                            w=w.capitalize()
                                            converts.append(
                                            self.parser.lemmatize(w)
                                            )
                                    elif iscapitalized(trythis) :
                                        converts = []
                                        for w in filter(None, wlist):
                                            w=w.lower()
                                            converts.append(
                                            self.parser.lemmatize(w)
                                            )
                                    else:  # word is all caps or a mixture
                                        converts = []
                                        for w in filter(None, wlist):
                                            w=w.lower()
                                            converts.append(
                                            self.parser.lemmatize(w)
                                            )
                                        for w in filter(None, wlist):
                                            w=w.lower().capitalize()
                                            converts.append(
                                            self.parser.lemmatize(w)
                                            )    
                                    try:
                                        # print("wlist=",wlist)
                                        stage2, glosslist2 = self.filter_parsed(converts, list(filter(None, wlist)))                                        
                                    except ValueError:
                                        print("WARNING4: invalid orthographic conversion result, skipping token:", token.type, token.value, converts)

                                else:
                                    # print("not self.converters token.value=",token.value)
                                    trythis2=""
                                    if token.value.islower():
                                        trythis=token.value.capitalize()
                                    elif iscapitalized(token.value):
                                        trythis=token.value.lower()
                                    else:
                                        trythis=token.value.lower()
                                        trythis2=token.value.lower().capitalize()
                                    try:
                                        stage2,glosslist2=self.parser.lemmatize(trythis)
                                    except ValueError:
                                        print("WARNING5: invalid orthographic conversion result, skipping token:", token.type, token.value, converts)

                                    if trythis2 != "":
                                        try:
                                            stage3,glosslist3=self.parser.lemmatize(trythis2)
                                            glosslist2=glosslist2+glosslist3
                                        except ValueError:
                                            print("WARNING6 ",trythis2," lemmatize error ")

                                if trythis != "":
                                    #gl2=""
                                    #for g in glosslist2: 
                                    #    gl2 +=str(g)+", "
                                    #print("glosslist2","["+gl2[:-2]+"]")

                                    if len(glosslist2)>0 and glosslist2!=glosslist:
                                        for g in glosslist2:
                                            if len(g.ps)>0 and g.ps[0] != "":
                                                nggok=0
                                                if g.gloss=="" :
                                                    if len(g.morphemes)>0 :
                                                        for gg in g.morphemes:
                                                            if len(gg.ps)==1 and gg.ps[0]!="mrph" and gg.gloss!="": nggok+=1
                                                else:
                                                    nggok=1

                                                if nggok>0:
                                                    if g in glosslist: continue
                                                    else: glosslist.append(g)

                                        # do some cleanup on resulting list
                                        glosslist2=glosslist
                                        glosslist=[]
                                        for g in glosslist2:
                                            if len(g.ps)>0 and g.ps[0] != "":
                                                nggok=0
                                                if g.gloss=="" :
                                                    if len(g.morphemes)>0 :
                                                        for gg in g.morphemes:
                                                            if len(gg.ps)==1 and gg.ps[0]!="mrph" and gg.gloss!="": nggok+=1
                                                else:
                                                    nggok=1

                                                if nggok>0:
                                                    if g in glosslist: continue
                                                    else: glosslist.append(g)                                        
                                        if len(glosslist) == 0 :
                                            glosslist=glosslist2    # no interesting results found!


                                        # MORE CLEANUP:
                                        # if len glosslist>1 éliminate X:n.prop:NOM artificial entries
                                        if len(glosslist)>1:
                                            glosslist2=glosslist
                                            glosslist=[]
                                            for g in glosslist2:
                                                if len(g.ps)>0:
                                                    if not (g.ps[0]=='n.prop' and g.gloss=='NOM'):
                                                        glosslist.append(g)
                                        if len(glosslist) == 0 :
                                            glosslist=glosslist2    # no interesting results found!

                                    #gl1=""
                                    #for g in glosslist: 
                                    #    gl1 +=str(g)+", "
                                    #print("solution found?:","["+gl1[:-2]+"]")

                        # needs testing here if it is the first Word in sentence (added wordindex)
                        # do "trythis" (try lower case - but also try uppercase if it's old bambara all in lowercase)
                        # and append to already found glosslist
                        # example Masalabolo may have identified Masala as TOP + bolo "branch"
                        # but it can also be masalabolo "text"
                        # print("(word) wordindex=",wordindex,"token=",token.value)
                        if wordindex==1:    
                            # caution: this is not beginning of sentence but is restarted at punctuations, ie: also after a comma

                            # assess initial situation, how many catitalized and lowercase results
                            gl1 =""
                            ncapitalized=0
                            nlowercase=0
                            # print("glosslist",glosslist)
                            for g in glosslist: 
                                if g.form[0].islower(): nlowercase+=1
                                else:                   ncapitalized+=1
                                gl1 +=str(g)+", "
                            #print("standard list for :",token.value,"glosslist:","["+gl1 [:-2]+"]")
                            #if      nlowercase==0:print("all capitalized")
                            #elif    ncapitalized==0:print("all lowercase")
                            #else:   print("mixed list lower and capitalized")

                            trythis=""

                            testthis=token.value[0]
                            if self.converters:
                                wlist = self.convert_orthography(token.value)
                                testthis = wlist[0]
                                if "-" in testthis: 
                                    wlist.append(testthis.replace("-",""))

                            if testthis.islower():    # was gloss.form
                                if ncapitalized == 0:  # not capitalized result in standard approach
                                    trythis=token.value.capitalize()   # no worry if converters (not used there), trythis just needs to be <> "
                                    if self.converters:
                                        # already done : wlist = self.convert_orthography(token.value)
                                        converts = []
                                        for w in filter(None, wlist):
                                            w=w.capitalize()
                                            converts.append(
                                            self.parser.lemmatize(w)
                                            )
                                        try:
                                            stage2, glosslist2 = self.filter_parsed(converts, list(filter(None, wlist)))
                                        except ValueError:
                                            print("WARNING2: invalid orthographic conversion result, skippig token:", token.type, token.value, converts)
                                    else: 
                                        stage2,glosslist2=self.parser.lemmatize(trythis)
                                    
                                    #gl2=""
                                    #for g in glosslist2: gl2+=str(g)+", "
                                    #print("islower trythis:",trythis,"glosslist2:","["+gl2[:-2]+"]")

                            else:                     # Word was capitalized
                                if nlowercase == 0 :  # no lowercase result in standard approach
                                    trythis=token.value.lower()   # no worry if converters (not used there), trythis just needs to be <> "
                                    if self.converters:
                                        # already done: wlist = self.convert_orthography(token.value)
                                        converts = []
                                        for w in filter(None, wlist):
                                            w=w.lower()
                                            converts.append(
                                            self.parser.lemmatize(w)
                                            )
                                        try:
                                            stage2, glosslist2 = self.filter_parsed(converts, list(filter(None, wlist)))
                                        except ValueError:
                                            print("WARNING3: invalid orthographic conversion result, skippig token:", token.type, token.value, converts)
                                    else: 
                                        stage2,glosslist2=self.parser.lemmatize(trythis)

                                    #gl2=""
                                    #for g in glosslist2: gl2+=str(g)+", "
                                    #print("not islower trythis:",trythis,"glosslist2:","["+gl2[:-2]+"]")
                                
                            if trythis!="":

                                    if glosslist2!=glosslist:
                                        for g in glosslist2:
                                            if len(g.ps)>0 :
                                                nggok=0
                                                if g.gloss=="" :
                                                    if len(g.morphemes)>0 :
                                                        for gg in g.morphemes:
                                                            if len(gg.ps)==1 and gg.ps[0]!="mrph" and gg.gloss!="": nggok+=1
                                                else:
                                                    nggok=1

                                                if nggok>0:
                                                    if g in glosslist: continue
                                                    else: glosslist.append(g)

                                    # nettoyage des doublons
                                    #   faut-il plus de nettoyage (gloses inutiles) ???

                                    glosslist2=glosslist
                                    glosslist=[]
                                    for g in glosslist2:
                                        if g not in glosslist:
                                            glosslist.append(g)

                                    if len(glosslist)==0:
                                        glosslist=glosslist2
                                    
                                    # MORE CLEANUP:
                                    # if len glosslist>1 éliminate X:n.prop:NOM artificial entries
                                    if len(glosslist)>1:
                                        glosslist2=glosslist
                                        glosslist=[]
                                        for g in glosslist2:
                                            if len(g.ps)>0:
                                                if not (g.ps[0]=='n.prop' and g.gloss=='NOM'):
                                                    glosslist.append(g)
                                    if len(glosslist) == 0 :
                                        glosslist=glosslist2    # no interesting results found!
                                    


                                #gl1 =""
                                #for g in glosslist: gl1 +=str(g)+", "
                                #print("Resulting glosslist:","["+gl1 [:-2]+"]")

                            #else: print("no change")

                        # 29/09/2025: move forms that are different from original at the end of the list
                        glistsame=[]
                        glistdiff=[]
                        if len(glosslist)>1 :
                            refform=re.sub(r'[\u0300\u0301\u0302\030c]','',token.value.lower())
                            # refform=re.sub(r'[\u0300\u0301\u0302\030c]','',wlist[0])
                            for g in glosslist:
                                thisform=re.sub(r'[\u0300\u0301\u0302\030c]','',g.form)
                                #print("refform, thisform",refform,thisform)
                                if thisform==refform:
                                    glistsame.append(g)
                                else:
                                    glistdiff.append(g)
                            glosslist=glistsame+glistdiff


                        if self.normalize_orthography and self.converters:
                            if len(wlist) == 1:
                                normform = wlist[0]
                            else:
                                case = self.get_case(wlist[0])
                                normforms = list(set([case(g.form) for g in glosslist]))
                                if len(normforms) == 1:
                                    normform = normforms[0]
                                else:
                                    normform = u'*{}*'.format(u'/'.join(normforms))
                            annot.append(daba.formats.WordToken(glosslist, normform, str(stage)))
                        else:
                            annot.append(daba.formats.WordToken(glosslist, token.value, str(stage)))





            self.parsed.append(par)
        return self.parsed


def load_plugins():
    plugins = {
        plugin.name: plugin.load()
        for plugin
        in pkg_resources.iter_entry_points('daba.plugins')
    }
    return plugins


def parse_file(infile, outfile, pp, args):
    print('Processing', infile)
    io = daba.formats.FileWrapper()
    io.read(infile, sentlist=args.sentlist)
    io.write(outfile, pp.parse(io.para), parsed=True, format=args.format)
    print('Finished', outfile)


def main():
    plugins = load_plugins()
    tkz = Tokenizer()

    aparser = argparse.ArgumentParser(description='Daba suite. Command line morphological parser.')
    aparser.add_argument('-i', '--infile', help='Input file (.txt or .html)', default="sys.stdin")
    aparser.add_argument('-o', '--outfile', help='Output file', default="sys.stdout")
    aparser.add_argument('-s', '--script', action='append', choices=plugins.keys(), default=None, help='Perform orthographic conversion operations (defined in plugins). Conversions will be applied in the order they appear on command line.')
    aparser.add_argument('-c', '--convert', action='store_true', help="Convert orthography")
    aparser.add_argument("-d", "--dictionary", action="append", help="Toolbox dictionary file (may be added multiple times)")
    aparser.add_argument("-g", "--grammar", help="Grammar specification file")
    aparser.add_argument("-n", "--noparse", action='store_true', help="Do not parse, only process resources")
    aparser.add_argument("-N", "--nolemmas", action='store_true', help="Do not lemmatize, only tokenize input")
    aparser.add_argument("-S", "--sentlist", action='store_true', help="Read txt file with sentence boundary tags")
    aparser.add_argument("-l", "--list", help="Read input filenames list from file")
    aparser.add_argument("-t", "--detone", action='store_true', help="Ignore tones in dictionary lookups")
    aparser.add_argument("-z", "--tokenizer", action='store', choices=tkz.methods, default="default", help="Tokenizer to use")
    aparser.add_argument("-f", "--format", action='store', choices=daba.formats.FileWrapper().output_formats, default="html", help="Output file format")
    aparser.add_argument("-v", "--verbose", action='store_true', help="print info messages on loaded dictionaries")
    args = aparser.parse_args()

    tkz.use_method(args.tokenizer)

    if args.nolemmas:
        pp = Processor(tokenizer=tkz, converters=args.script, detone=args.detone, nolemmas=True, normalize_orthography=args.convert)
    else:
        dl = DictLoader(verbose=args.verbose)
        gr = GrammarLoader()
        if args.dictionary:
            for dicfile in args.dictionary:
                dl.addfile(dicfile)
        if args.grammar:
            gr.load(args.grammar)
    if not args.noparse:
        if not args.nolemmas:
            pp = Processor(dictloader=dl, grammarloader=gr, tokenizer=tkz, converters=args.script, detone=args.detone, normalize_orthography=args.convert, has_sentences=args.sentlist)
        if args.list:
            with open(args.list, encoding='utf-8') as filelist:
                for line in filelist:
                    infile = os.path.normpath(line.strip())
                    if os.path.exists(infile):
                        outfile = os.path.splitext(infile)[0] + '.pars.html'
                        parse_file(infile, outfile, pp, args)
        else:
            parse_file(args.infile, args.outfile, pp, args)
    exit(0)


if __name__ == '__main__':
    main()

