Grammar definition file
=======================

Grammar definition file contains morphoptactic rules used by daba parser 
to classify and split wordforms into morphemes. Logically grammar file 
consists of two parts:

* List of patterns describing formal cues to extract morphemes from a wordform. 
  Each pattern is simultaneously a rule to extract a particular morpheme and a constraint
  on possible contexts where such extraction is applicable.
* Instructions controlling the order of application of patterns.

Parser splits input text into word tokens and processes them one by one.
For each word a list of possible grammatical interpretations is produced.
If dictionary for the given language is available, dictionary lookups 
may be inserted into the parsing procedure.


Syntax of the grammar file is described in more detail below.

Gloss objects
-------------

Each word is transformed into a gloss object. Result of the parsing of the word 
is a list of gloss objects. Gloss object consists of four fields:

* form — a wordform string;
* part of speech tag;
* gloss — translation, lemma or standardized grammatical marker;
* list of morphemes comprising this wordform where each morpheme is also a regular gloss object.

Since gloss object is a recursive data structure, ti may represent an arbitrary tree-like 
structure of the wordform, such as morphemes nesting.


Structure of a gloss object is represented in grammar definition file with help of formal notation::

    form:PoS_tag:gloss [ morpheme:PoS_tag:gloss :: ]

Form, PoS tag and gloss are written in this order and separated with colons 
(no spaces between them are allowed). Any part of the triple (values for form, PoS and gloss) 
may be omitted, but a pair of colons is obligatory. This triple may be followed by optional 
morphemes list enclosed in brackets. Each morpheme — also a gloss object — inside the
list is written as a form—PoS—gloss triple. Morphemes in a list are separated by white space.

Please note, that each wordform may have more than one part of speech tag: one top-level 
tag for the whole word and a separate part of speech tag for each morpheme. 
There's no need for part of speech tags of the wordform and morphemes to coincide,
rather in most cases they are different. E.g. a word may be a noun that consists of
the verbal stem and a nominalizing affix. This may be written like this::

    :n: [ :v: :n: ]

Pattern
-------

Pattern is the main building unit of morphological processing in daba. 
Technically, pattern is a declarative statement which consists of two parts:

#. Select gloss. 

   Gloss object describing context where the pattern is applicable. 

#. Mark gloss.

   Gloss object describing labels that should be assigned to the fields of the resulting 
   gloss object after application of the pattern. 

In grammar definition file each pattern is written on a separate line in a form::

    pattern select_gloss | mark_gloss

Keyword ``pattern`` starts a line and is followed by select and mark glosses separated with vertical bar.


Extracting morphemes
~~~~~~~~~~~~~~~~~~~~

One of the main uses for patterns in daba is splitting words into morphemes. 
For this aim there is a special splitter expression used in place of gloss object form::

    {part|part|part}

Splitter expression consists of list of segments enclosed in braces and separated by vertical bar. 
Each segment should match part of the wordform and all splitter expression should match a whole wordform,
not part of it. Any part of a splitter expression may be:

* *string*, matches literally;
* a python *regular expression*, enclosed in html-style tags ``<re></re>``;
* *empty*, matches any remaining part of the word (greedy).

Vertical bars mark points where a morpheme boudary should be drawn in a resulting gloss.
For example, splitter expression ``{|na}`` will transform gloss ``banna::`` with no morphemes 
into ``banna:: [ ban:: na:: ]`` with two morphemes ``ban-na``. Note that form ``bannan`` will not 
be matched in this expression, since there's a trailing ``n`` that doesn't match the last segment
in splitter expression and hence the word couldn't be matched as a whole.

Splitter expressions may only be used in morphemes list of the splitter gloss in pattern statement.
Select gloss for our example rule to extract ``-na`` morpheme will look like this::

    :: [ {|na}:: ]

Testing for context
~~~~~~~~~~~~~~~~~~~

Another use for patterns in daba is expressing morphotactic constraints on the order 
of the morphemes in a wordform. Most often such constraints are expressed in terms of
possible combinations of part of speech tags. 

For example, to state that ``-na`` morpheme may only be used in nouns we should fill part of speech 
feature in our select gloss::

    :n: [ {|na}:: ]

This means that only glosses marked as nouns will be processed by our rule. Note that if gloss have
no part of speech mark, it will be also mathed by this rule. 

Other frequent use case is constraint on part of speech tags of stems in composite words. An example
select gloss for this case may look like this::

    :n: [ :n: :v: ]

Which means that in a noun composite of two stems first stem should be noun and second — verb. 


Marking
~~~~~~~

The second task performed by application of the pattern is marking of the resulting gloss object.  
Let's take again our example with ``banna``. We must not only split word into stem and affix,
but also mark the affix with a particular gloss and mark the stem with appropriate part of speech
tag, possible in combination with this particular affix. These marks are written in a mark gloss
of the pattern statement. The whole statement will look like this::

    pattern :n: [ {|na}:: ] | :n: [ :n: :mrph:GLOSS ]

Note that in mark gloss there's two morphemes in morpheme list whereas in select gloss there's 
only one. This is because mark part is applied to the gloss after application of the select part 
which results in splitting of the single form into two morphemes. Affix ``-na`` is marked with 
``GLOSS`` and ``mrph`` tag, and stem receives ``n`` PoS tag and the whole word is marked with ``n``. 
As a result of application of this pattern gloss object ``banna::`` will be transformed 
into ``banna:n: [ ban:n: na:mrph:GLOSS ]``.


