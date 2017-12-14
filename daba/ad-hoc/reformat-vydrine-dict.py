#!/usr/bin/python

import sys
import re
from collections import namedtuple

Field = namedtuple('Field', 'tag value')

def parse_line(line):
    line = line.decode('utf-8').strip()
    if line.startswith("\\"):
        tag, space, value = line[1:].partition(" ")
        value = value.strip()
        return Field(tag, value)
    return Field(None, None)

def is_lexeme(record):
    if record:
        return record[0].tag == 'lx'
    return False

def is_ref(record):
    tags = [f.tag for f in record]
    return 'rfe' in tags or 'rfr' in tags

def dialect_is_maninka(value):
    return bool(re.search(u'\\bm', value))

def is_headword_border(field):
    if field.tag in ['ps' 'ex' 'idi']:
        return True
    if field.tag == 'va' and ';' in field.value:
        return True

def headword_is_maninka(record):
    dialects = []
    for field in record:
        if field.tag == 'di' and field.value:
            dialects.append(field.value)
        if is_headword_border(field):
            break
    if dialects:
        return any([dialect_is_maninka(dialect) for dialect in dialects])
    else:
        return True

def is_sense_border(field):
    return field.tag in ['ms', 'msn', 'msv']

def strip_sense_number(record):
    output = []
    for field in record:
        if field.tag == 'lx':
            output.append(Field('lx', re.sub(u'[0-9.]+$', '', field.value)))
        else:
            output.append(field)
    return output

def split_polisemous_records(record):
    output = []
    head = []
    inhead = True
    sense = []
    for field in record:
        if field.tag == 'msp':
            inhead = False
            if sense:
                output.append(head + sense)
                sense = []
        if inhead:
            head.append(field)
        else:
            sense.append(field)
    output.append(head + sense)
    return output

def split_affixed_records(record):
    output = []
    head = []
    affix = []
    lx = ''
    ps = ''
    inhead = True
    for field in record:
        if field.tag == 'lx':
            if u' ' in field.value:
                lx = field.value[:field.value.find(u' ')]
            else:
                lx = field.value
        if field.tag == 'ps' and not ps:
            ps = field.value
        if field.tag == 'af':
            inhead = False
            if affix:
                if 'ps' not in [f.tag for f in affix]:
                    affix.append(Field('ps', ps))
                output.append(affix)
                affix = []
            if head:
                output.append(head)
                head = []
            newlx = Field('lx', field.value.replace(u'~', lx))
            affix.append(newlx)
        else:
            if inhead:
                head.append(field)
            else:
                affix.append(field)
    if head:
        output.append(head)
    if affix:
        if 'ps' not in [f.tag for f in affix]:
            affix.append(Field('ps', ps))
        output.append(affix)
    return output

def rename_gloss_fields(record):
    seen = []
    output = []
    glossfields = ['dfr', 'dfe', 'dff']
    for field in record:
        if field.tag in glossfields:
            if not field.tag in seen:
                seen.append(field.tag)
                output.append(Field('g'+field.tag[2], field.value))
            else:
                output.append(Field('gv'+field.tag[2], field.value))
        else:
            output.append(field)
    return output

def cut_examples(record):
    output = []
    inex = False
    for field in record:
        if field.tag in ['ex', 'idi', 'vad']:
            inex = True
            continue
        if inex:
            inex = False
            if field.tag == 'di':
                continue
        output.append(field)
    return output

def cut_bamana_variants(record):
    output = []
    variants = []
    afterva = False
    for field in record:
        if field.tag == 'va':
            variants.append(field)
            afterva = True
        elif field.tag == 'di' and afterva:
            if dialect_is_maninka(field.value):
                if variants:
                    output.extend(variants)
                    variants = []
                output.append(field)
            else:
                if variants:
                    variants = []
        else:
            if variants:
                output.extend(variants)
                variants = []
            output.append(field)
    return output

def cut_bamana_senses(record):
    output = []
    sense = []
    sense_is_bamana = False
    insense = False
    for field in record:
        if is_sense_border(field):
            if not insense:
                insense = True
            else:
                if not sense_is_bamana:
                    output.extend(sense)
                sense = []
                sense_is_bamana = False
        if insense:
            sense.append(field)
        else:
            output.append(field)
        if field.tag == 'di' and not dialect_is_maninka(field.value) and insense:
            sense_is_bamana = True
    if sense and not sense_is_bamana:
        output.extend(sense)
    return output

def is_obscure_record(record):
    tags = [field.tag for field in record]
    is_obscure = True
    for tag in ['ps', 'ge', 'gr', 'gf']:
        if tag in tags:
            is_obscure = False
    return is_obscure

def split_variants(record):
    output = []
    for field in record:
        if field.tag in ['va', 'lx'] and not value_is_empty(field.value):
            varlist = filter(None, re.split(u'[,;] ', field.value))
            if field.tag == 'va':
                variants = [Field('va', var) for var in varlist]
            else:
                variants = []
                variants.append(Field('lx', varlist[0]))
                for var in varlist[1:]:
                    variants.append(Field('va', var))
            output.extend(variants)
        else:
            output.append(field)
    return output

def replace_bamana_lx(record):
    output = []
    lxhead = []
    inlx = True
    replace = False
    for field in record:
        if is_headword_border(field) or is_sense_border(field):
            if inlx:
                inlx = False
                output.extend(lxhead)
                lxhead = []
        if field.tag == 'va':
            if inlx:
                inlx = False
                if replace:
                    output.append(Field('lx', field.value))
                    lxhead = []
                    continue
                else:
                    #output.extend(lxhead)
                    lxhead.append(field)
#            else:
#                output.append(field)
        if inlx:
            if field.tag == 'di':
                if field.value.strip() and not dialect_is_maninka(field.value):
                    replace = True
            lxhead.append(field)
        else:
            output.append(field)
    if lxhead:
        output = lxhead + output
    return output

def retonalize_value(value):
    value = value.strip()
    if ' ' in value:
        return value
    lowindex = value.find(u'\u0300')
    if lowindex > 0:
        head = value[:lowindex]
        tail = value[lowindex:].replace(u'\u0301', '')
        value = head + tail 
    value = value.replace(u'\u030c', u'\u0300')
    return value

def retonalize_record(record):
    output = []
    for field in record:
        if field.tag in ['lx', 'va']:
            output.append(Field(field.tag, retonalize_value(field.value)))
        else:
            output.append(field)
    return output

def value_is_empty(value):
    stripped = value.strip()
    if not stripped:
        return True
    if stripped.isspace():
        return True
    return False

def cut_empty_fields(record):
    output = []
    for field in record:
        if not value_is_empty(field.value):
            output.append(field)
    return output

def cleanup_record(record):
    output = []
    record = cut_empty_fields(record)
    record = cut_examples(record)
    preserve = ['lx', 'nk', 'va', 'ps', 'ms', 'msp', 'dfr', 'dfe', 'dff', 'di', 'af', 'rfr', 'rfe', 'vl', 'sn', 'sme', 'smf', 'smr', 'msv', 'itm', 'syn', 'qsyn', 'ethr', 'ethe', 'ethf', 'use', 'usr', 'egr', 'ege', 'egf']
    for field in record:
        if field.tag in preserve:
            output.append(field)
    return output

def serialize_record(record):
    for field in record:
        line = u'\\{0} {1}\n'.format(*field).encode('utf-8')
        sys.stdout.write(line)
    sys.stdout.write("\n")



records = []
fields = []
with open(sys.argv[1]) as f:
    for line in f:
        field = parse_line(line)
        if field.tag is None:
            if is_lexeme(fields):
                records.append(fields)
            fields = []
            continue
        fields.append(field)

preprocessed = []
for record in records:
    if not is_ref(record):
#        serialize_record(record)
        record = cleanup_record(record)
#        serialize_record(record)
        record = split_variants(record)
#        print "BEFORE"
#        serialize_record(record)
        record = replace_bamana_lx(record)
#        serialize_record(record)
        record = strip_sense_number(record)
#        serialize_record(record)
        senses = split_polisemous_records(record)
        for sense in senses:
            affixes = split_affixed_records(sense)
            for affix in affixes:
                preprocessed.append(affix)

for record in preprocessed:
    if headword_is_maninka(record):
#        print "RECORDS"
#        serialize_record(record)
        record = cut_bamana_variants(record)
#        serialize_record(record)
        record = cut_bamana_senses(record)
#        serialize_record(record)
        record = split_variants(record)
#        serialize_record(record)
        record = retonalize_record(record)
#        serialize_record(record)
        record = rename_gloss_fields(record)
        if not is_obscure_record(record):
            serialize_record(record)




