#! /usr/bin/env python
# coding=utf-8

import sys, math, unicodedata
from collections import Counter, defaultdict
import Levenshtein
from syllables import syllabify, vowels
import re

# Installation of prerequisites
# sudo pip install python-Levenshtein

# Constant lists
markers_tone  = [unichr(0x0300),unichr(0x0301),unichr(0x0302),unichr(0x030c)]
token_seperator = u'_'
code_seperator = u'_'
mode_indicators = u'+-'
mode_names   = [u"insert",u"delete"]
markers_to_be_ignored = u"[].-" + code_seperator
markers_to_be_replaced = {u"’":u"'"}

# todo : decomposition en opérations - opérands
def code_dispatcher(code) :

    lst = []
    for i in mode_indicators :
        lst.append("")
        lst.append("")

    if not code : return lst
    if code[-1] == code_seperator : code = code[: -1]
    code_segments = code.split(code_seperator)
    for i in range(0, len(code_segments), 3) :
        m, p, c = code_segments[i : i + 3]
        lst[mode_indicators.index(m) + len(mode_indicators) * int(c in markers_tone)] += \
            u"{}{}{}{}{}{}".format(m, code_seperator, p, code_seperator, c, code_seperator)

    return lst

def code_resort(code) :

    ret = []
    if not code : return code
    if code[-1] == code_seperator : code = code[: -1]
    code_segments = code.split(code_seperator)
    for i in range(0, len(code_segments), 3) :
        m, p, c = code_segments[i : i + 3]
        ret.append(u"{}{}{}{}{}{}".format(m, code_seperator, p, code_seperator, c, code_seperator))

    ret = sorted(ret, key=lambda x : int(mode_indicators.index(m))+2*int(x.split(code_seperator)[1]))
    ret = ''.join(ret)
    if ret : ret = ret[:-1]

    return ret

def _get_features_customised_for_tones(tokens, idx):

    feature_list = []

    if not tokens:
        return feature_list

    try :
        token = tokens[idx]
    except IndexError :
        raise

    # positon du syllabe actuel et préfixe et suffixe du même mot
    lst = []
    for i in range(idx, len(tokens) + 1, 1) :
        try :
            if tokens[i] == token_seperator :
                lst.append(i)
                if len(lst) >= 2 :
                    break
        except IndexError :
            lst.append(i)
            break

    try :
        feature_list.append("SYLLABE_ID1_" + str(lst[0] - idx))
    except :
        pass

    try :
        feature_list.append("SUFFIXE_ACTUEL_" + tokens(lst[0] - 1))
    except :
        pass

    lst2 = []
    for i in range(idx, -2, -1) :
        try :
            if tokens[i] == token_seperator :
                lst2.append(i)
                if len(lst2) >= 2 :
                    break
        except IndexError :
            lst2.append(i)
            break

    try :
        feature_list.append("SYLLABE_ID2_" + str(idx - lst2[0]))
    except :
        pass

    try :
        feature_list.append("PREFIXE_ACTUEL_" + tokens(lst2[0] + 1))
    except :
        pass

    # préfixe et suffixe du mots précédent et suivant dans la même phrase
    try :
        prefixe_du_mot_suivant = tokens[lst[0] + 1]
        feature_list.append("PREFIXE_SUIVANT_" + prefixe_du_mot_suivant)
    except IndexError :
        pass
    try :
        suffixe_du_mot_precedent = tokens[lst2[0] - 1]
        feature_list.append("SUFFIXE_PRECEDENT_" + suffixe_du_mot_precedent)
    except IndexError:
        pass

    try :
        suffixe_du_mot_suivant  = tokens[lst[1] - 1]
        feature_list.append("SUFFIXE_SUIVANT_" + suffixe_du_mot_suivant)
    except IndexError :
        pass
    try :
        prefixe_du_mot_precedent = tokens[lst2[1] + 1]
        feature_list.append("PREFIXE_PRECEDENT_" + prefixe_du_mot_precedent)
    except IndexError :
        pass

    # Capitalization
    if token[0].isupper():
        feature_list.append('CAPITALIZATION')

    # Number
    if re.search(r'\d', token) is not None:
        feature_list.append('IL_Y_A_UN_CHIFFRE')

    # Punctuation
    punc_cat = set(["Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po"])
    if all (unicodedata.category(x) in punc_cat for x in token):
        feature_list.append('PONCTUATION_PURE')

    # Voyelles
    voyelles = ""
    for c in token :
        if c.lower() in vowels:
            voyelles += c
    feature_list.append('VOYELLES_'+ voyelles)

    # Syllabes précédent et suivant
    try :
        feature_list.append('SYLLABE_PRECEDENT_' + token[idx - 1])
    except IndexError :
        pass

    try :
        feature_list.append('SYLLABE_SUIVANT_' + token[idx + 1])
    except IndexError :
        pass

    feature_list.append('SYLLABE_ACTUEL_' + (token))

    # Suffix & prefix up to length 3
    if len(token) > 1:
        feature_list.append('SUF_' + token[-1:])
        feature_list.append('PRE_' + token[:1])
    if len(token) > 2:
        feature_list.append('SUF_' + token[-2:])
        feature_list.append('PRE_' + token[:2])
    if len(token) > 3:
        feature_list.append('SUF_' + token[-3:])
        feature_list.append('PRE_' + token[:3])

    return feature_list

def repr (c, null = "", spaces = False) :
    if not c : return null
    else :
        if spaces :
            return " " + rm_sep(c) + " "
        else:
            return rm_sep(c)

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

    for k in markers_to_be_replaced.keys() : token = token.replace(k, markers_to_be_replaced[k])
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
    #    des tokens et la liste contenant chacune de ses formes tonales

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
    def __init__(self) :
        self.form_non_tonal = Counter()
        self.form_tonal     = Counter()
        self.code           = Counter()
        self.segment_code   = Counter()
        self.dict_code      = defaultdict()
        self.dict_form_tonal= defaultdict()
        self.num   = 0
        self.err_cnt = 0
        self.cnt_ops = 0
        self.mode = Counter()
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

        ret += u"Distribution sur : \n"
        ret += u"\tLes opérations d'édition : \n" + sprint_cnt(self.mode, u"\t\t",-1,20)
        ret += u"\tL'ensemble des codes par syllabe : \n" + sprint_cnt(self.code, u"\t\t",-1,20)
        ret += u"\tL'ensemble des codes par leur segment atomique : \n" + sprint_cnt(self.segment_code, u"\t\t",-1,20)
        ret += u"\tL'ensemble des caractères supprimés : \n" + sprint_cnt(self.src_delete, u"\t\t",-1,20)
        ret += u"\tL'ensemble des caractères inserés : \n" + sprint_cnt(self.dst_insert, u"\t\t",-1,20)

        if self.err_cnt :
            ret += u"\nErreur : nombre d'erreurs rencontrés dans le codage = {}\n".format(self.err_cnt)
        return ret

class encoder_tones () :

    def __init__ (self) :
        self.src = ""
        self.dst = ""
        self.p_src = 0
        self.p_dst = 0
        self.ret = ""
        self.chunks = []
        self.stat = statistique()

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

    """
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
    """

    def differential_encode (self, form_non_tonal, form_tonal, seperator = True) :

        self.p_src = -1
        self.p_dst = -1

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
                self.delete()

            elif mode == "insert" :
                self.insert()

            else : # mode == "replace"
                self.insert()
                self.delete()

        # enlèvement du séparateur du code à la fin du chunk
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

        # internal auto-check
        form_tonal_reproduced = repr(''.join([self.differential_decode(chunk, code) for code, chunk in zip(self.ret,self.chunks)]))
        if form_tonal_reproduced :
            form1 = reshaping(repr(unicodedata.normalize('NFD', form_tonal_reproduced)), False)
            form2 = reshaping(repr(unicodedata.normalize('NFD', form_tonal)),False)
            if form1 != form2 :
                self.stat.err_cnt += 1

        if seperator :
            self.ret.append(u'')
            self.chunks.append(token_seperator)

        return [self.ret, self.chunks]

    def report (self) :
        print self.stat.__str__()

    def differential_decode (self, chunk, code) :

        chunk = reshaping(chunk, False)

        if len(code.strip()) == 0 : return chunk

        if code[-1] == code_seperator : code = code[: -1]
        code_segments = code.split(code_seperator)
        if len(code_segments) % 3 != 0 : print code ; print (code_segments) ; print ("input code incorrect !"); exit(1)

        p_offset = 0
        for i in range(0,len(code_segments),3) :
            try :
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
            else : # elif m == mode_indicators[mode_names.index('insert')] :
                try : l = chunk[: p_eff]
                except IndexError : l = ''
                try : r = chunk[p_eff  :]
                except IndexError : r = ''
                chunk = l + c + r
                p_offset += 1

        return chunk

def main () :

    forms_non_tonal = [u'tò',u'yerehré',u'ò',u'e', u'òhehòhe', u'òhòh',u'ohoh',u'ehe', u'tò',u'hééh',u'heeh',u'hèé', u'narè']
    forms_tonal     = [u'tɔ',u'yɛrɛ̂hre',u'o',u'é', u'ohéhohé', u'ohoh',u'òhòh',u'ebe',u'tɔ',u'heeh',u'hééh',u'héè', u'nàrɛ']

    enc = encoder_tones()

    for form_non_tonal, form_tonal in zip(forms_non_tonal, forms_tonal) :
        print u"Source      {}".format(reshaping(form_non_tonal, False))
        print u"Destination {}".format(reshaping(form_tonal, False))
        [codes, chunks] = enc.differential_encode (form_non_tonal, form_tonal)
        i = 0
        for chunk, code in zip(chunks, codes) :
            sys.stdout.write(u"Syllabe_{} '{}' - '{}' -> '{}'\n".format(i, enc.differential_decode(chunk, code), chunk, repr(code)));
            sys.stdout.write(u"Syllabe_{} '{}' - '{}' -> '{}'\n".format(i, enc.differential_decode(chunk, code_resort(''.join(code_dispatcher(code)))), chunk, repr(code_resort(''.join(code_dispatcher(code))))));
            pass
        print ""

        form1 = repr(''.join([enc.differential_decode(chunk, code) for code, chunk in zip(codes, chunks)]))
        form2 = repr(''.join([enc.differential_decode(chunk, code_resort(''.join(code_dispatcher(code)))) for code, chunk in zip(codes, chunks)]))
        if form1 != form2 :
            print form1, form2

    enc.report()

if __name__ == "__main__" : main()
