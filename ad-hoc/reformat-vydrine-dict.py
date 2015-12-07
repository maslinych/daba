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

def contains_maninka(record):
    if field.tag == 'di' and field.value:
        if dialect_is_maninka(field.value):
            return True
    return False

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
    return field.tag in ['ms', 'msn']

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
    inhead = True
    for field in record:
        if field.tag == 'lx':
            lx = field.value[:field.value.find(u' ')]
        if field.tag == 'af':
            inhead = False
            if affix:
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
    filtered_record = []
    inex = False
    for index, field in enumerate(record):
        if record[index].tag in ['ex', 'idi']:
            inex = True
        elif field.tag == 'di' and inex:
            inex = False
        else:
            filtered_record.append(field)
    return filtered_record

def cut_bamana_variants(record):
    output = []
    variants = []
    for field in record:
        if field.tag == 'va':
            variants.append(field)
        elif field.tag == 'di':
            if variants:
                if dialect_is_maninka(field.value):
                    output.extend(variants)
                variants = []
            else:
                output.append(field)
        else:
            if variants:
                output.extend(variants)
                variants = []
            else:
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
        if field.tag == 'di' and not dialect_is_maninka(field.value):
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
        if field.tag == 'va':
            varlist = filter(None, re.split(u'[,;] ', field.value))
            variants = [Field('va', var) for var in varlist]
            output.extend(variants)
        else:
            output.append(field)
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

def cleanup_record(record):
    output = []
    record = cut_examples(record)
    preserve = ['lx', 'nk', 'va', 'ps', 'ms', 'msp', 'dfr', 'dfe', 'dff', 'di', 'af', 'rfr', 'rfe']
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
        record = cleanup_record(record)
        record = strip_sense_number(record)
        senses = split_polisemous_records(record)
        for sense in senses:
            affixes = split_affixed_records(sense)
            for affix in affixes:
                preprocessed.append(affix)

for record in preprocessed:
    if headword_is_maninka(record):
        record = cut_bamana_variants(record)
        record = cut_bamana_senses(record)
        record = split_variants(record)
        record = retonalize_record(record)
        record = rename_gloss_fields(record)
        if not is_obscure_record(record):
            serialize_record(record)




