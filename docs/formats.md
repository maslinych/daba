## Daba HTML file format

HTML files produced by Daba parser and disambiguation utility hold all
metadata for the file, source text split into sentences and tokens
with morpholoical annotation (probably ambiguous) for each token.

### Metadata

Metadata is stored in the HTML `<head>` element inside `<meta>` tags.
All metadata is structured as an associative array (list of
key—value pairs) and represented as a series of `<meta>` elements.

Metadata field name is stored the `name` attribute of the `<meta>` tag
and value for the field is stored in the `content` attribute.

For example:

```HTML
<meta content="text/html; charset=utf-8" http-equiv="Content-Type" />
<meta content="Jama" name="source:title" />
<meta content="Information : Intervention publique" name="text:genre" />
<meta content="02.11.2008" name="text:date" />
<meta content="3-5" name="text:pages" />
<meta content="Bamako" name="source:address" />
```

Allowed metadata fields depend on the corpus and are defined in the
config file used by the [metadata editor utility](../daba/meta.py).

A sample config file defining a list of metadata fields and allowed
values for them can be found [in samples directory](./samples/meta.xml).


### Paragraphs and sentences

Input text file is split by the parser into paragraphs and sentences.

An empty line (`\n\n`) is treated as a paragraph separator. Each
source paragraph corresponds to a `<p>` element in HTML body.

Sentence splitting is done basing on the tokenization procedure
(currently built into the [parser](../daba/mparser.py), see `Tokenizer`
class). Sentences are split at the sentence punctuation `SentPunct`
token.

Each sentence corresponds to a `<span>` element with an attribute
`class="sent"`. A content of the element holds the sentence
text — a verbatim fragment from the source text file. Sentence text is
followed by the list of `<span>` elements with `class="annot"` holding
morphological annotation for each token in the sentence.

For example:

```HTML
<p>
	<span class="sent">&lt;h&gt;Kalanko ni ladamuni forobajɛkafɔ&lt;/h&gt;
		<span class="annot">...</span>
	</span>
	...
</p>
```

### Token-level annotation

Annotation for each token in the sentence has two levels:

1. Token class, to distinguish between non-word and word tokens.
2. For word tokens — a list of possible morphological
   interpretations.

Annotation for a token is represented by a `<span>` element.

#### Token class

Token class is indicated by the `class` attribute with following
allowed values:

* `class="c"` — punctuation;
* `class="w"` — word token.
* `class="t"` — HTML tag in the source file used to markup document
  structure. Such tags are inserted by the operators and should be
  preserved in the annotation. **Obsolete**, should be replaced by `c`.

Token string is kept in the element content.

Sentence without any morphological annotation would look like:

```HTML
<span class="sent">A test.
	<span class="annot">
		<span class="w">A</span>
		<span class="w">test</span>
		<span class="c">.</span>
	</span>
```

#### Parsing and ambiguity status

For each word token general information on the token's parsing stage
and ambiguity status is provided in the `stage` attribute of the
token's `<span>` element.

Daba parser provides value for the `stage` attribute based on the
latest grammar rule that matched during token processing. The names
for the stages are defined in the grammar specification file as a
first argument to the `stage` directives. An example can be found in
the [sample grammar](./sample/bamana.gram.txt).

A special value `stage="-1"` means that no rule in the grammar matched
this token.

A special value `stage="tokenizer"` is reserved by a parser for the
numeric tokens which are treated as word tokens with PoS tag `num`.

A special value `stage="gdisamb.0"` is reserved by a disambiguation
utility. This means that token has been disambiguated manually by the
operator.


#### Lemmas and variants

For the word tokens additional morphological annotation is
provided. Morphological annotation is put in the nested `<span>` element
with `class="lemma"` immediately after the token string.

If the token has more than one possible parses other interpretations
are put inside the first lemma span in the nested `<span>` elements
with `class="lemma var"`.

Text of each `lemma` or `lemma var` element represents normalized form
for the lemma. PoS tag and Gloss for the lemma are put after the form
in the `<sub>` elements with the corresponding `class="ps"` and
`class="gloss"` tags. If a lemma has no PoS or gloss corresponding
`<sub>` element will not be present in the HTML representation.

An example of a token with two possible morphological interpretations:

```HTML
<span class="w" stage="0">na <!-- token string -->
	<span class="lemma">ná <!-- first lemma -->
		<sub class="ps">n</sub> <!-- PoS for the first lemma -->
		<sub class="gloss">"Monsieur"</sub> <!-- Gloss for the first lemma-->
		<span class="lemma var">ná <!-- second lemma-->
			<sub class="ps">pp</sub> <!--PoS for the second lemma -->
			<sub class="gloss">dans</sub> <!--Gloss for the second lemma-->
		</span>
	</span>
</span>
```

#### Morpheme-level annotation

Morphological annotation in Daba is a recursive data structure (Gloss
object) that can contain a nested list of morphemes, each being itself
a Gloss object (probably with own list of morphemes etc.).

List of morphemes for a lemma (Gloss object) is optional and is often
missing.

In Daba's HTML format list of morphemes inside a lemma is represented
by a list of `<span>` elements with `class="m"` nested in the lemma's
`<span>` element. Each morpheme span usually have it's own nonempty
PoS and gloss in the corresponding `<sub>` elements.

For example, following lemma `taara` has two morphemes `taa` and `ra`.

```HTML
<span class="lemma">taara
	<sub class="ps">v</sub>
	<span class="m">táa
		<sub class="ps">v</sub>
		<sub class="gloss">aller</sub>
	</span>
	<span class="m">ra
		<sub class="ps">mrph</sub>
		<sub class="gloss">PFV.INTR</sub>
	</span>
</span>
```



