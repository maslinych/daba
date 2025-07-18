#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""Dabased is a stream editor (sed) for files with linguistic
annotation in Daba format.

Dabased performs batch replacements in daba annotation accorging to
the rules defined in a script file. For each rule, dabased runs
through the annotated tokens in daba file trying to apply the
transformation defined by the rule as many times as possible. Text
segments where the rule is applied can not overlap.

Script file syntax
==================

Rules
-----

Dabased script file is a simple text file with a list of replacement
rules to apply to a file, one rule on a line. Empty lines and lines
starting with # symbol are ignored.

Each rule has a form::

    pattern >> replacement

where

 * a pattern is an expression that defines a fragment of annotation
   that the rule matches;
 * a replacement is a list of tokens to insert.

Expressions
-----------

Each expression is a list of tokens separated by '++'.
Each token may be either:

* a Gloss in a unicode notation::

    words:n:gloss [word:n:gloss s:mrph:PL]

A Gloss may be not fully specified. If such a partial expression
appears in the left side of the rule (a pattern), the match is
perfomed accorging to :method:`Gloss.matches()` logic. If a partial
expression appears in the replacement part, the information in the
source token and the replacement pattern is united according to
:method:`Gloss.union()` logic.

* a PlainToken, in the following syntax:

    @type

or

    @type:regex

where

* type — is a string matching `PlainToken.type`;
* regex — is a regular expression that is matched against the whole
  `PlainToken.value`.

The PlainToken expressions are not meant to be used for 'w' token type
(WordToken, regular words). Use Gloss expressions instead.

Expression Examples
-------------------

* :n: — matches any noun

* he:pers:3SG — matches personal pronoun 'he' with specified
part of speech tag and gloss.

* :pers: ++ :v: — matches personal pronoun followed by any verb

* @<s> ++ @</s> — matches a sentence opening tag immediately followed
  by a sentence closing tag (an empty sentence).

* @</s>:\n+ — matches a sentence closing tag where sentence text
  consists only of one or more newline symbols (no words in a
  sentence).

Types of Rules
--------------

There are three distinct types of rules with slightly different
replacement logic.

1. One-to-one Gloss replacement rule:

    he:pers:HE >> he:pers:3SG

This is the most common and historically the first use case for
dabased. It is used to tweak glosses and other annotation fields for
the text that has already been annotated.

Note that the rule of this type is applied recursively to all
embedded glosses (morhemes at any level of annotation). This allows to
make replacements in stems occurring in any compound and derivative
forms.

2. Many-to-many replacement rules:

    @<s> ++ i:pers:1sg >> @<s> ++ i:pers:1sg

This type of rules applies to a window of several sequential tokens,
either word tokens (Glosses) or others. The replacement part should
have an equal number of tokens. The replcement is perfomed using
:method:`WordToken.union()` or :method:`PlainToken.union()` in the
given order. The union is done only for the root Glosses, morphemes
are not processed recursively.

3. Asymmetric replacement rules:

    @<s> ++ @</s> >>

Asymmetric rules are any rules that have different number of tokens on
the left and right sides of the rule. The replacement part of these
rules is simply substituted instead of a list of source tokens where
the rule matches. No union is done with the source tokens, so the
replacement tokens should be fully specified (no partial Glosses are
allowed).

Asymmetric rules may be used for token splitting and merging. A
special case of asymmetric rules are deletion rules, with an empty
right side.

"""


import sys
import re
import argparse
from funcparserlib.lexer import LexerError
from funcparserlib.parser import NoParseError
from collections import namedtuple
from itertools import islice, zip_longest
import unicodedata as u

import daba.formats
import daba.grammar


class ReplaceRule(namedtuple('ReplaceRule', 'inlist outlist')):
    __slots__ = ()

    @property
    def winsize(self):
        return len(self.inlist)

    @property
    def symmetric(self):
        return len(self.inlist) == len(self.outlist)


class ScriptParser(object):
    def __init__(self, scriptfile):
        self.commands_list = []
        with open(scriptfile, encoding='utf-8') as script:
            for command in script:
                if not command.isspace() and not command.startswith('#'):
                    self.commands_list.append(self.parse_command(command))
        self.commands_list = filter(None, self.commands_list)

    def __iter__(self):
        for rule in self.commands_list:
            yield rule

    def parse_gloss(self, gloss_string):
        gloss = daba.grammar.fullgloss_parser().parse(
            daba.grammar.tokenize(gloss_string)
        )
        gt = daba.formats.WordToken([gloss], stage='dabased')
        #print("*** parse_gloss / gt :",gt)
        return gt

    def parse_token(self, token_expression):
        try:
            toktype, tokvalue = token_expression[1:].split(':')
            tokvalue = re.compile(r"^" + tokvalue + r"\Z", re.UNICODE)
        except (ValueError):
            toktype = token_expression[1:]
            tokvalue = ''
        #print("--- parse_token returns:",daba.formats.PlainToken((toktype, tokvalue)))
        return daba.formats.PlainToken((toktype, tokvalue))

    def parse_expr(self, expr):
        glosslist = [i.strip()
                     for i in re.split(r'\+\+', expr)
                     if i not in ['++', ''] and not i.isspace()]
        result = []
        for gexpr in filter(None, glosslist):
            try:
                if gexpr.startswith('@'):
                    result.append(self.parse_token(gexpr))
                else:
                    result.append(self.parse_gloss(gexpr))
            except (LexerError, NoParseError, ValueError) as e:
                sys.stderr.write(u'In rule: {0}'.format(gexpr))
                sys.stderr.write(u'{}\n'.format(e))
                return []
        return result

    def parse_command(self, command):
        # command = u.normalize('NFKD', command).strip('\n')
        # normalize should concern lemmas, not gloss
        def normalizeLex(m):
            lx=m.groups()[0]
            lx=u.normalize('NFKD', lx)
            psgloss=m.groups()[1]
            psgloss=u.normalize('NFC',psgloss) # is this faster than tomonolith() ?
            return lx+psgloss

        command = command.strip('\n')
        command = re.sub(r'([^\:\< ]+)(\:[^\:\< ]*\:[^\:\< ]*)',normalizeLex,command)

        m = re.match(r'\s*(.+?)\s*>>\s*(.+?)\s*$', command, re.U)
        try:
            source, target = m.groups()
        except (AttributeError):
            sys.stderr.write(u'Malformed rule: {0}\n'.format(command))
            return
        sourcelist = self.parse_expr(source)
        targetlist = self.parse_expr(target)
        #print("=== parse_command / targetlist:", targetlist) # OK
        return ReplaceRule(sourcelist, targetlist)


class StreamEditor(object):
    def __init__(self, verbose=False):
        self.dirty = False
        self.verbose = verbose

    def getstr(self, tokens):
        return u' ++ '.join([str(token) for token in tokens])

    def feed_tokens(self, winsize, stream=()):
        pos = 0
        it = iter(stream)
        window = tuple(islice(it, winsize))
        if len(window) == winsize:
            yield pos, window
        for token in it:
            window = window[1:] + (token,)
            pos += 1
            yield pos, window

    def match(self, tokenlist, pattern):
        # for token, intoken in zip(tokenlist, pattern):
        #     sys.stderr.write(
        #         u'{}\tIN: {} PAT: {}\n'.format(
        #             token.matches(intoken),
        #             token,
        #             intoken
        #         )
        #     )
        return all(
            token.matches(intoken)
            for token, intoken in zip(tokenlist, pattern)
        )

    def replace(self, token, target):
        if token.type == 'w':
            outgloss = token.union(target)
            if outgloss.gloss is not None:
                target = outgloss
        #print("replace / target:", target)
        return target

    def recursive_replace(self, gloss, pattern, target, filler):
        #if gloss is None : return gloss # why do I need this protection???
        filler+="   "
        #print(filler+"gloss, pattern, target :\n"+filler,gloss,"\n"+filler, pattern,"\n"+filler, target)
        if gloss.matches(pattern, psstrict=True):
            out = gloss.union(target, psoverride=True)
        else:
            out = gloss
            # print(filler+"+++ recursive_replace / before gloss.morphemes : out :",out)
            
            lpattern=len(str(pattern))
            # question: is it relevant to compare size of pattern and size of glosses in all cases, are there exceptions ?
            if out.morphemes:
                # print(filler+"+++ recursive_replace / gloss.morphemes :",out.morphemes)
                outstr0=str(out)
                if lpattern<=len(outstr0):
                    outstr=outstr0[:outstr0.find("[")+1]   #: "kɛ́ra:v: ["
                    isNone=False
                    for subgloss in out.morphemes:
                        if subgloss is None:
                            print("recursive_replace WHY? outstr0=",outstr0)
                            isNone=True
                        else:
                            if lpattern<=len(str(subgloss)):
                                subgloss=self.recursive_replace(subgloss,pattern,target,filler)
                            outstr+=str(subgloss)+" "
                    outstr=outstr[:-1]+"]"
                    # print(filler+"outstr:",outstr)
                    if isNone or outstr[outstr.find("["):].startswith("[ ")\
                        or outstr[outstr.find("["):].endswith("[ "):  # suppression cases
                        print(filler+"recursive_replace strange outstr=",outstr)
                        outstr,ignore=outstr.split(" [",1)
                    if outstr != outstr0 :
                        toks = daba.grammar.str_tokenize(outstr)
                        try:
                            out = daba.grammar.stringgloss_parser().parse(toks)
                            # print(filler+"daba.grammar out=",out)
                        except:
                            print("stringloss_parser failed on:",outstr)
                            # no change to out ?

            # else: print(filler+"no gloss.morphemes")

            """
            print(filler+"self.recursive_replace(morph, pattern, target) for morph in gloss.morphemes :\n"+filler,\
                        tuple(self.recursive_replace(morph, pattern, target, filler) for morph in gloss.morphemes))
            out = out._replace(
                morphemes=tuple(
                    self.recursive_replace(morph, pattern, target,filler)
                    for morph in out.morphemes)
            )
            """
            

        # print(filler+"+++ recursive_replace / returns out :",out)
        return out



    def make_replace_func(self, rule):
        # print("\n!!! make_replace_func rule:",self.getstr(rule.inlist)," >> ",self.getstr(rule.outlist))
        global textscript
        if not rule.symmetric:
            def replace_func(tokens, rule):
                # in rule.outlist, words should be compatible with meta-data text-script
                # example outlist:
                # [w ('bɛ́', 'dabased', [Gloss(form='bɛ́', ps=('cop',), gloss='BE', morphemes=())]) None, 
                #  w ('kà', 'dabased', [Gloss(form='kà', ps=('pm',), gloss='INF', morphemes=())]) None]
                # print("modify outlist per text-script:", textscript)
                for w in rule.outlist:
                    # print ("w.token:",w.token)
                    if textscript=='Ancien orthographe malien': # ref corbama/meta.xml
                        w.token=re.sub(r'[̀́̌̂]','',w.token) # remove tones
                        w.token=w.token.replace('ɛɛ','èe')
                        w.token=w.token.replace('ɔɔ','òo')
                        w.token=w.token.replace('ɛ','è')
                        w.token=w.token.replace('ɔ','ò')
                        w.token=w.token.replace('ɲ','ny')
                        w.token=w.token.replace('ƐƐ','ÈE')
                        w.token=w.token.replace('ƆƆ','ÒO')
                        w.token=w.token.replace('Ɛ','È')
                        w.token=w.token.replace('Ɔ','Ò')
                        
                        w.token=w.token.replace('Ɲ','Ny')
                    elif textscript=="N’Ko":    # ref cormani/meta.xml
                        def s(a,b,text):
                          return(re.sub(a,b,text,0,re.U|re.MULTILINE))

                        def gbarali(m):
                          #text=s(r'([^ߊߍߋߌߐߏߎ ])(?P<WOV1>[ߊߍߋߌߐߏߎ])([́̀̂̌]*)([^ߊߍߋߌߐߏߎ́̀̂̌])(?P=WOV1)([^\u07F2])','\g<1>\g<4>\g<2>\g<3>\g<5>',text)
                          cons1=m.groups()[0]
                          cons2=m.groups()[3]
                          voy=m.groups()[1]  # unique since voy1=voy2
                          ton1=m.groups()[2]
                          nonasal=m.groups()[4]
                          ton2=""
                          if nonasal in '\u0300\u0301\u0302\u030C\u07EF\u07F0\u07EE\u07F1': ton2=nonasal   # latin tones + nko tones for already identified long wovels

                          if cons1==cons2 : return cons1+voy+ton1+cons2+voy+nonasal
                          else:             
                            if ton2==ton1 : return cons1+cons2+voy+nonasal
                            else :
                              if ton1=='\u0301':  # high tone
                                if ton2=="": return cons1+cons2+voy+nonasal          # pas de ton2=high tone too
                                else:        return cons1+voy+ton1+cons2+voy+nonasal
                              # is the reverse situation ton1=="" and ton2="\u301" the same ???
                              else:          return cons1+voy+ton1+cons2+voy+nonasal

                        def lat2nko(text):
                          text=text.strip().lower()
                          
                          texts=""
                          #
                          # text should end with a punctuation
                          if text[-1] not in " ,.;:!?\n": text=text+"\n"
                          scan=re.findall(r'([^ ,\.;:!\?\n]+)([ ,\.;:!\?\n]+)',text)
                          #print(scan)
                          nitem=len(scan)
                          iitem=0
                          for item in scan:
                            iitem+=1
                            w=item[0]
                            punct=item[1]

                            w=re.sub(r'([aeiouɛɔ][\u0300\u0301\u0302\u030C]*)n([^aeiouɛɔ])',r'\g<1>~\g<2>',w)
                            w=re.sub(r'([aeiouɛɔ][\u0300\u0301\u0302\u030C]*)n$',r'\g<1>~',w)
                            
                            first=re.findall(r'(^([aeiouɛɔ])([\u0300\u0301\u0302\u030C]*)(~?))',w)
                            lfirst=0
                            if first:
                              lfirst=len(first[0][0])
                              # print(w,'first',first[0][0])
                            syllabs=re.findall(r'(([^aeiouɛɔ])([aeiouɛɔ])([\u0300\u0301\u0302\u030C]*)([aeiouɛɔ]?)(~?))',w[lfirst:])
                            # caution long vowels : formula above assumes up to two vowels but they could be different!!!
                            # print(w,"\nsyllabs",syllabs)

                            # do something useful with syllabs data
                            nsyl=len(syllabs)
                            if nsyl>1:
                              if first: basetone=first[0][2]
                              else:     basetone=syllabs[0][3]
                              # print("basetone",basetone.encode("unicode_escape"))
                              # is basetone a low tone ?
                              if basetone=="\u0300": 
                                # check tone of next word if any
                                basetone2=""
                                if iitem!=nitem:  # next word not to be checked on last word
                                  w2=scan[iitem][0]
                                  # print("next word",w2)
                                  if w2[0] in "aeiouɛɔ": basetone2=w2[1]
                                  else:                  basetone2=w2[2]
                                  # print("basetone2",basetone2.encode("unicode_escape"))
                                if basetone2!="\u0301":
                                  # update final tone to high
                                  wnew=''
                                  if first: wnew=first[0][0]
                                  isyl=0
                                  for syl in syllabs:
                                    isyl+=1
                                    if isyl==nsyl:
                                      wnew=wnew+syl[1]+syl[2]+"\u0301"+syl[4]+syl[5]
                                    else:
                                      wnew=wnew+syl[0]
                                  w=wnew

                            w=w.replace("~","n")
                            texts=texts+w+punct
                          text=texts
                          # print("new text\n",text,"\n")

                          ###### NY closed list follows: ######
                          text=s(r'\bbɛnnyɔɔnya\b','ߓߍ߲ߢߐ߲߱ߧߊ',text)
                          text=s(r'\bdɛnnyɔgɔnnya\b','ߘߍ߲߬ߢߐ߬ߜߐ߲߬ߧߊ',text)
                          text=s(r'\bsiginyɔgɔnnya\b','ߛߜߌ߬ߢߐ߬ߜߐ߲߬ߧߊ',text)
                          text=s(r'\byilanyilan\b','ߦߌߟߊ߲ߦߌߟߊ߲',text)
                           
                          text=s(r'\bdɛnyɔonnu\b','ߘߍ߲߬ߢߐ߲߰ߣߎ',text)
                          # опечатка, должно быть dɛ̀nɲɔɔnnu
                          text=s(r'\bdɛnyɔɔ\b','ߘߍ߬ߢߐ߲߰',text)
                          # неправильное написание, надо dɛ̀ɲɔɔn 
                          text=s(r'\bnadanya\b','ߣߊߘߊ߲ߢߊ',text)
                          # nadanya  = nadannya
                          text=s(r'(ɲinynkali|ɲunynkali)','ɲininkali',text)
                          # some typo
                          #####################################
                          text=s(r'\bny','ߢ',text)
                           

                          ###### nny -> nɲ -> n+NYA-woloso
                          text=s(r'\bnny','ߒߧ',text)
                          text=s(r'nny','\u07F2\u07E7',text) # ߲ Nazalization Mark + ߧ Nya Woloso
                          ######  ny ->  ɲ
                          text=s(r'ny','ߢ',text)
                          #####################################

                          #text=s(r'ng','ߢ߭',text)    # incompatible avec le gb ! julakolongbɛ
                          text=s(r'\bng','ߢ߭',text)    # est seul possible
                          text=s(r'ŋ','ߢ߭',text)
                          
                          text=s(r'\bn\'','ߣߴ',text)

                          #? essai de traitement des nasales voyelle + U+07F2=߲
                          #!!! LES TONS NE SONT PAS TRAITES DANS lat2nko.pl !!!
                          # NB: IMPORTANT! la nasalisation doit précéder le ton
                          text=s(r'([aeiouɛɔ])([́̀̂]*)n\b',r'\g<1>\u07F2\g<2>',text)
                          text=s(r'([aeiouɛɔ])([́̀̂]*)n([bcdefghjklmnprstwyz])',r'\g<1>\u07F2\g<2>\g<3>',text)

                          # Replace initial n followed by a wovel with ߒ , others initial n with ߣ
                          text=s(r'\bn([^aeiouɛɔn])',r'ߒ\g<1>',text)
                          text=s(r'\bn','ߣ',text)

                          # où sont traitées les nasales ? <----------------------------
                         
                          # Replace n at the end of a word with ߒ        # ???
                          text=s(r'([aeiouɛɔ])n\b',r'\g<1>ߒ',text)
                          text=s(r'([aeiouɛɔ])n([^aeiouɛɔ])',r'\g<1>ߒ\g<2>',text)
                          text=s(r'\bn\b','ߒ',text)
                          text=s(r'n','ߣ',text)
                          
                          text=s(r'gb','ߜ',text)
                          text=s(r'sh','ߛ߭',text)
                          text=s(r'ʃ','ߛ߭',text)
                          text=s(r'th','ߛ߳',text)
                          text=s(r'θ','ߛ߳',text)
                          text=s(r'kp','ߜ߳',text)
                          text=s(r'rr','ߚ',text)
                          text=s(r'g','ߜ߭',text)
                          text=s(r'v','ߝ߭',text)
                          text=s(r'z','ߖ߭',text)
                          text=s(r'ħ','ߤ߭',text)
                          text=s(r'kh','ߞ߭',text)
                          text=s(r'x','ߞ߭',text)
                          text=s(r'q','ߞ߫',text)
                          text=s(r'gh','ߜ߫',text)
                          text=s(r'ɣ','ߜ߫',text)
                          text=s(r'zh','ߗ߭',text)
                          text=s(r'dj','ߗ߭',text)
                          text=s(r'ʒ','ߗ߭',text)
                          text=s(r'ð','ߗ߭',text)
                          text=s(r'ʕa','ߊ߳',text)
                          text=s(r'ʕ','ߊ߳',text)
                          text=s(r'bh','ߓ߭',text)
                          text=s(r'ɓ','ߓ߭',text)
                          text=s(r'dh','ߘ߳',text)
                          text=s(r'ɗ','ߘ߳',text)
                          
                          text=s(r'b','ߓ',text)
                          text=s(r'c','ߗ',text)
                          text=s(r'd','ߘ',text)
                          text=s(r'f','ߝ',text)
                          text=s(r'h','ߤ',text)
                          text=s(r'j','ߖ',text)
                          text=s(r'k','ߞ',text)
                          text=s(r'l','ߟ',text)
                          text=s(r'm','ߡ',text)
                          text=s(r'ɲ','ߢ',text)
                          text=s(r'p','ߔ',text)
                          text=s(r's','ߛ',text)
                          text=s(r't','ߕ',text)
                          text=s(r'r','ߙ',text)
                          text=s(r'w','ߥ',text)
                          
                          text=s(r'y','ߦ',text)
                          
                          text=s(r'aa','ߊ߯',text)
                          text=s(r'ɛɛ','ߍ߯',text)
                          text=s(r'ee','ߋ߯',text)
                          text=s(r'ii','ߌ߯',text)
                          text=s(r'ɔɔ','ߐ߰',text)    # erreur ?
                          text=s(r'oo','ߏ߯',text)
                          text=s(r'uu','ߎ߯',text)

                        # add transforms with inside latin tone
                        # high
                        #  with tonal article
                          text=s(r'áa`','ߊ߮',text)
                          text=s(r'ɛ́ɛ`','ߍ߮',text)
                          text=s(r'ée`','ߋ߮',text)
                          text=s(r'íi`','ߌ߮',text)
                          text=s(r'ɔ́ɔ`','ߐ߮',text)
                          text=s(r'óo`','ߏ߮',text)
                          text=s(r'úu`','ߎ߮',text)
                        #  without
                          text=s(r'áa','ߊ߯',text)
                          text=s(r'ɛ́ɛ','ߍ߯',text)
                          text=s(r'ée','ߋ߯',text)
                          text=s(r'íi','ߌ߯',text)
                          text=s(r'ɔ́ɔ','ߐ߯',text)
                          text=s(r'óo','ߏ߯',text)
                          text=s(r'úu','ߎ߯',text)
                        # low
                        #  with tonal article  
                          text=s(r'àa`','ߊ߱',text)
                          text=s(r'ɛ̀ɛ`','ߍ߱',text)
                          text=s(r'èe`','ߋ߱',text)
                          text=s(r'ìi`','ߌ߱',text)
                          text=s(r'ɔ̀ɔ`','ߐ߱',text)
                          text=s(r'òo`','ߏ߱',text)
                          text=s(r'ùu`','ߎ߱',text)
                        #   without
                          text=s(r'àa','ߊ߰',text)
                          text=s(r'ɛ̀ɛ','ߍ߰',text)
                          text=s(r'èe','ߋ߰',text)
                          text=s(r'ìi','ߌ߰',text)
                          text=s(r'ɔ̀ɔ','ߐ߰',text)
                          text=s(r'òo','ߏ߰',text)
                          text=s(r'ùu','ߎ߰',text)

                        # single wowels
                          text=s(r'a','ߊ',text)
                          text=s(r'á','ߊ',text)   # usage ???
                          text=s(r'ɛ','ߍ',text)
                          text=s(r'e','ߋ',text)
                          text=s(r'i','ߌ',text)
                          text=s(r'ɔ','ߐ',text)
                          text=s(r'o','ߏ',text)
                          text=s(r'u','ߎ',text)
                          
                        #  text=s(r'^(.)',' \1',text) ; text=s(r'(.)$','\1 ',text)
                        #  text=s(r'([^\d])(\d)(\d)(\d)(\d)(\d)(\d)(\d)([^\d])','\1\8\7\6\5\4\3\2\9',text)
                        #  text=s(r'([^\d])(\d)(\d)(\d)(\d)(\d)(\d)([^\d])','\1\7\6\5\4\3\2\8',text)
                        #  text=s(r'([^\d])(\d)(\d)(\d)(\d)(\d)([^\d])','\1\6\5\4\3\2\7',text)
                        #  text=s(r'([^\d])(\d)(\d)(\d)(\d)([^\d])','\1\5\4\3\2\6',text)
                        #  text=s(r'([^\d])(\d)(\d)(\d)([^\d])','\1\4\3\2\5',text)
                        #  text=s(r'(\D)(\d)(\d)(\D)','\1\2\3\4',text)
                        #  
                        #  s/^ //g ; s/ $//g
                          
                          text=s(r'0','߀',text)
                          text=s(r'1','߁',text)
                          text=s(r'2','߂',text)
                          text=s(r'3','߃',text)
                          text=s(r'4','߄',text)
                          text=s(r'5','߅',text)
                          text=s(r'6','߆',text)
                          text=s(r'7','߇',text)
                          text=s(r'8','߈',text)
                          text=s(r'9','߉',text)

                          text=s(r'<ߤ>','<h>',text)
                          text=s(r'<\/ߤ>','</h>',text)
                        # s/<\/ߤ>/<\/h>/g
                          text=s(r'<ߛ>','<s>',text)
                          text=s(r'<\/ߛ>','</s>',text)
                        # s/<\/ߛ>/<\/s>/g
                          text=s(r'<ߕ>','<t>',text)
                          text=s(r'<\/ߕ>','</t>',text)
                        # s/<\/ߕ>/<\/t>/g
                          text=s(r'<ߕߓ>','<tb>',text)
                          text=s(r'<\/ߕߓ>','</tb>',text)
                        # s/<\/ߕߓ>/<\/tb>/g
                          text=s(r'<ߓߙ>','<br>',text)
                          text=s(r'<\/ߓߙ>','</br>',text)
                          text=s(r'<ߓߙ\/>','<br/>',text)
                        # s/<ߓߙ\/>/<br\/>/g

                          # GBARALI - ex bála
                          # NB: check wovels with latin tones included, 
                          # skipped if nazalisation character ex bálan
                          #  (1st wovel :not included with tones)
                          #  (2d wovel: explicit)
                          
                          # checkit=re.findall(r'([^ߊߍߋߌߐߏߎ])(?P<WOV1>[ߊߍߋߌߐߏߎ])([́̀̂̌]*)([^ߊߍߋߌߐߏߎ́̀̂̌])(?P=WOV1)([^\u07F2])',text)
                          # if checkit: print(checkit)
                          # else : print("not found")

                          # à revoir : le ton initial n'est pas à reporter, du coup la règle nɔnɔ ne peut pas être traitée comme ça.
                          #text=s(r'([^ߊߍߋߌߐߏߎ ])(?P<WOV1>[ߊߍߋߌߐߏߎ])([́̀̂̌]*)([^ߊߍߋߌߐߏߎ́̀̂̌])(?P=WOV1)([^\u07F2])','\g<1>\g<4>\g<2>\g<3>\g<5>',text)
                          # solution : renvoi à une fonction adhoc  - tons latins : [\u0300\u0301\u0302\u030C] + tones for long wovels: 07EF et 07F0
                          text=re.sub(r'([^ߊߍߋߌߐߏߎ ])(?P<WOV1>[ߊߍߋߌߐߏߎ])([\u0300\u0301\u0302\u030C\u07EF\u07F0\u07EE\u07F1]*)([^ߊߍߋߌߐߏߎ́̀̂̌])(?P=WOV1)([^\u07F2])',\
                                      gbarali,text,0,re.U|re.MULTILINE)

                          # tones character references checked / https://unicodeplus.com
                          # reference  latin 
                          #    high ́  Combining Acute Accent (U+0301)
                          #    low ̀  Combining Grave Accent (U+0300) 
                          #    descending ̂  Combining Circumflex Accent (U+0302)
                          #    raising ̌  Combining Caron (U+030C)
                          #    tonal article Grave Accent (U+0060) `
                          #
                          # reference N'ko
                          #    long wovels
                          #       H+flottant B Nko Combining Long Descending Tone (U+07EE) ߮
                          #       H Nko Combining Long High Tone (U+07EF) ߯
                          #       B Nko Combining Long Low Tone (U+07F0) ߰
                          #       Ascendant+flottant B Nko Combining Long Rising Tone (U+07F1) ߱
                          #
                          #    short wovels
                          #       H Nko Combining Short High Tone (U+07EB) ߫
                          #       H+flottant B   (none, default)
                          #       B Nko Combining Short Low Tone (U+07EC) ߬
                          #       Ascendant+flottant B Nko Combining Short Rising Tone (U+07ED) ߭

                          # remove high tones
                          #? text=s('́','',text)

                          # high tones
                          #   long wovels
                          #     no final tone=high tone???
                          text=s(r'(?P<WOV1>[ߊߍߋߌߐߏߎ])(?P=WOV1)\b',r'\g<1>\u07EE',text)
                          #     high tone expressed
                          text=s(r'(?P<WOV1>[ߊߍߋߌߐߏߎ])\u0301(?P=WOV1)',r'\g<1>\u07EF',text)
                         
                          #   short wovels
                           #     no final tone=high tone???
                          text=s(r'([ߊߍߋߌߐߏߎߒ][\u07F2]*)([ ,;\.\:\?\!])',r'\g<1>\u07EB\g<2>',text)  # en fin de mot sans autre indication !!! fin=espace ici ??? \b fails
                          text=s(r'([ߊߍߋߌߐߏߎߒ][\u07F2]*)$',r'\g<1>\u07EB',text)  # en fin de mot sans autre indication !!! fin=espace ici ??? \b fails
                          
                          text=s(r'([ߊߍߋߌߐߏߎߒ][\u07F2]*)\u0060',r'\g<1>',text)
                           #     high tone expressed
                          text=s(r'([ߊߍߋߌߐߏߎߒ][\u07F2]*)\u0301([ ,;\.\:\?\!])',r'\g<1>\u07EB\g<2>',text)  # ex bɔ́ en fin de mot ON SUPPOSE QUE C'EST UN VERBE!!!!!! fin=espace ici ??? \b fails
                          text=s(r'([ߊߍߋߌߐߏߎߒ][\u07F2]*)\u0301\u0060',r'\g<1>',text) # ex bɔ́` art tonal indique un NOM: supprimer
                          text=s(r'([ߊߍߋߌߐߏߎߒ][\u07F2]*)\u0301',r'\g<1>',text)  # ailleurs: supprimer

                          # low tones
                          #   long wovels
                          text=s(r'(?P<WOV1>[ߊߍߋߌߐߏߎ])\u0300(?P=WOV1)\u0060',r'\g<1>\u07F1',text)  # mɔ̀ɔ`
                          text=s(r'(?P<WOV1>[ߊߍߋߌߐߏߎ])\u0300(?P=WOV1)',r'\g<1>\u07F0',text) # mɔ̀ɔnin
                          #   short wovels
                          text=s(r'([ߊߍߋߌߐߏߎ][\u07F2]*)\u0300\u0060',r'\g<1>\u07ED',text) # l'art tonal indique un NOM
                          text=s(r'([ߊߍߋߌߐߏߎ][\u07F2]*)\u0300',r'\g<1>\u07EC',text)

                          # descending tones
                          #   long wovels 
                          text=s(r'(?P<WOV1>[ߊߍߋߌߐߏߎ])\u0302(?P=WOV1)',r'\g<1>\u07F1',text)   # aâ ? test case to find!
                          #   short wovels
                          text=s(r'([ߊߍߋߌߐߏߎߒ][\u07F2]*)\u0302',r'\g<1>',text)   # supprimer? (comme ce qui est fait pour ân 1PL)
                          
                          # remove leftover art. tonal [some cases not handled properly]
                          text=s(r'[\u0060\u0300\u0301\u0302]','',text)

                          # 1SG et 2SG sans ton # 07/01/2023 : 
                          #   NB: done in sentence scan (latin script preparation) but no effect ???
                          #   \b not working here but ok in Sublime text ???
                          #   text=s(r'\b([ߒ|ߌ])\u07EB\b','\g<1>',text)   # \b([ߒ|ߌ])߫\b
                          text=s(r'^([ߒ|ߌ])\u07EB ',r'\g<1> ',text)
                          text=s(r' ([ߒ|ߌ])\u07EB ',r' \g<1> ',text)  # relies on proper punctuation ;-)


                          # déplacer les ponctuations APRES LES TONS as it kills \b and latin punctuation tests fail

                          text=s(r',','،',text)
                          text=s(r'\?','؟',text)
                          text=s(r'!','߹',text)
                          text=s(r';','؛',text)
                          text=s(r'\'','ߴ',text)
                          
                          text=s(r'([߹؟،߸!\.:\(\)\-\u2329\u232A«»])\s*$',r'\g<1>\u200F',text) # 〈 Left-Pointing Angle Bracket + 〉 Right-Pointing Angle Bracket
                        # RTL mark after punctuation (U+200F Right-To-Left Mark)
                          text=s(r'([߹؟،߸!\.:\(\)\-\u2329\u232A«»])\s*<',r'\g<1>\u200F<',text) 
                        # RTL mark after punctuation

                          return(text[:-1])   # in dabased, remove trailing \n
                          
                        w.token=lat2nko(w.token)      # simplified version ignores -la -da in verbs - still too big a hammer!
                    # print ("-> w.token:",w.token)
                return rule.outlist
            domatch = True
        else:
            # FIXME special case for 1:1 replacement: allows deep matching
            # now supposedly fixed : need restructuring all this code instead of the following dirty fix!
            if rule.winsize == 1 and rule.inlist[0].type == 'w':
                if rule.inlist[0].gloss.morphemes and rule.outlist[0].gloss.morphemes and False:  # ============dirty fix 
                    # print("¹¹¹ rule si morphemes G et D :",self.getstr(rule.inlist)," >> ",self.getstr(rule.outlist))
                    def replace_func(tokens, rule):
                        token = tokens[0]
                        target = rule.outlist[0]
                        gt = self.replace(token, target)
                        outgloss = gt.gloss._replace(morphemes=target.gloss.morphemes)
                        gt = daba.formats.WordToken([outgloss], token=tokens[0].token, stage='dabased')
                        # print("### make_replace_func / gt:",gt)
                        return [gt]
                    domatch = True
                    #tried domatch = False
                else:
                    # print("²²² rule si pas morphemes G et D :",self.getstr(rule.inlist)," >> ",self.getstr(rule.outlist))
                    def replace_func(tokens, rule):
                        # print("###2 make_replace_func / tokens, rule:",tokens, rule)
                        token = tokens[0].gloss
                        # print("###2 make_replace_func / token:",token)
                        pattern = rule.inlist[0].gloss
                        # print("###2 make_replace_func / pattern :",pattern)
                        target = rule.outlist[0].gloss
                        # print("###2 make_replace_func / target:",target)
                        outgloss = self.recursive_replace(token, pattern, target,"")
                        # print("###2 make_replace_func / outgloss:",outgloss) # NOT OK
                        gt = daba.formats.WordToken([outgloss], token=tokens[0].token, stage='dabased')
                        # print("replace_func gt:",gt)
                        
                        """
                        # what is the justification for this test, it blocks changes 
                        # like prn -> mrph in gloss like in
                        # jɛ̀ɲɔgɔn:n:associé [jɛ̀:v:assembler ɲɔ́gɔn:prn:RECP] >> jɛ̀ɲɔgɔn:n:associé [jɛ̀:v:assembler ɲɔgɔn:mrph:RECP]
                        #  it will return jɛ̀ɲɔgɔn:n:associé [jɛ̀:v:assembler  ]
                        #  ... which fails
                        if pattern.ps == target.ps:
                            print("###2 make_replace_func / same ps      / tokens[0].union(gt):",tokens[0].union(gt))
                            print("###2 make_replace_func / same ps      / au lieu de      gt :",gt)
                            return [tokens[0].union(gt)]

                        else:
                            print("###2 make_replace_func / different ps / gt:",gt)
                            return [gt]
                        """
                        return [gt]
                    domatch = False
                    # tried (stops early!) domatch = True
            else:
                def replace_func(tokens, rule):
                    return [self.replace(token, target)
                            for token, target
                            in zip(tokens, rule.outlist)]
                domatch = True
        return (domatch, replace_func)

    def apply_rule(self, rule, stream):
        global nchanges
        # print("\n??? apply_rule / rule :",self.getstr(rule.inlist)," >> ",self.getstr(rule.outlist),"\n") # OK
        domatch, replace_func = self.make_replace_func(rule)
        # sys.stderr.write(u'Domatch {}\n'.format(str(domatch)))
        success = -rule.winsize
        #print("rule, rule.winsize, stream:",rule, rule.winsize, stream)
        #print("self.feed_tokens(rule.winsize, stream) : ",self.feed_tokens(rule.winsize, stream))
        for pos, tokens in self.feed_tokens(rule.winsize, stream):
            if pos < success + rule.winsize:
                continue
            if (
                    (not domatch and tokens[0].type == 'w')
                    or
                    (domatch and self.match(tokens, rule.inlist))
            ):
                # sys.stderr.write(
                #     u'match: {}\n'.format(self.getstr(tokens))
                # )
                # print("??? apply_rule / tokens passed to replace_tokens    :",self.getstr(tokens))   # NOT OK
                # print("??? apply_rule / rule   passed to replace_rule      :",self.getstr(rule.inlist)," >> ",self.getstr(rule.outlist))
                replacement = replace_func(tokens, rule)
                # print("??? apply_rule / replacement :",self.getstr(replacement))  # NOT OK
                # sys.stderr.write(
                #     u'replacement: {}\n'.format(self.getstr(replacement))
                # )
                # print("check all =")
                # for g, r in zip_longest(tokens, replacement, fillvalue=daba.formats.PlainToken()):
                #    print("g, r, = : ",g,r, g == r)
                # print("-?-",all(g == r for g, r in zip_longest(tokens, replacement, fillvalue=daba.formats.PlainToken())))
                if not all(g == r for g, r
                           in zip_longest(
                               tokens,
                               replacement,
                               fillvalue=daba.formats.PlainToken())):
                    self.dirty = True
                    nchanges+=1
                    if self.verbose:
                        sys.stderr.write(
                            u'\033[1m{0}\033[0m -> \033[92m{1}\033[0m\n'.format(
                                self.getstr(tokens),
                                self.getstr(replacement))
                            )
                    tokens = replacement
                    success = pos
                    for token in tokens:
                        yield token
                    continue
            yield tokens[0]
        else:
            if 'tokens' in locals():      # why did I need to protect from an error here?
                for token in tokens[1:]:
                    yield token

    def apply_script(self, script, stream):
        tokens = stream
        for rule in script:
            # if self.verbose: print("~~~ apply_script / rule in script :",rule, "list(tokens):",list(tokens)) # OK
            tokens = self.apply_rule(rule, list(tokens))
        #if self.verbose: print("~~~ apply_script / returns tokens :",list(tokens)) 
        return tokens


def main():

    aparser = argparse.ArgumentParser(description='Stream editor for files in Daba format')
    aparser.add_argument('infile', help='Input file (.html)')
    aparser.add_argument('-o', '--outfile', help='Output file', default=None)
    aparser.add_argument('-s', '--script', help='File with edit commands', required=True)
    aparser.add_argument('-v', '--verbose', help='Print info messages', action='store_true')
    args = aparser.parse_args()
    if not args.outfile:
        args.outfile = args.infile
    # start processing
    if args.verbose:
        sys.stderr.write(u'Processing {0} with rules from {1}...\n'.format(args.infile, args.script))
    sed = StreamEditor(verbose=args.verbose)
    script = ScriptParser(args.script)
    in_handler = daba.formats.HtmlReader(args.infile, compatibility_mode=False)
    #print("metadata:",in_handler.metadata)
    #print("textscript",in_handler.metadata['text:script'])
    global textscript
    textscript=in_handler.metadata['text:script']
    # print("script, in_handler:",script, in_handler)
    global nchanges
    nchanges=0
    processed_tokens = list(sed.apply_script(script, in_handler))
    if sed.dirty:
        out_handler = daba.formats.HtmlWriter((in_handler.metadata, in_handler.make_compatible_glosses(processed_tokens)), args.outfile)
        out_handler.write()
        if args.verbose:
            sys.stderr.write(u'Written {0} : \033[3m{1} changes\033[0m\n'.format(args.outfile,nchanges))


if __name__ == '__main__':
    main()
