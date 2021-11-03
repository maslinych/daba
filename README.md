## Daba — Pattern-based morphemic analysis toolkit

Daba is a rule-based morphological analysis package. Users familiar
with [Linguists' Toolbox by SIL](https://software.sil.org/toolbox/)
may regard Daba as a tool for the similar task of morpheme-by-morpheme
glossing. This type of annotation is known in linguistic typology and
anthropological linguistics as Interlinear Glossed Text (IGT) format.

The difference from Toolbox is that daba performs parsing
non-interactively, producing a list of all possible parses for each
word. The parser uses the list of morphological pattern rules defined
by the user in the [grammar file](./docs/grammar.rst). The user may
later disambiguate the parsed text using GUI included in Daba.

Daba provides a set of cross-platform GUI and CLI tools required to
provide full cycle of corpus annotation followed by manual
disambiguation:

* morphological parser [GUI](./daba/gparser.py) and [CLI](./daba/mparser.py)
  version
* [Metadata editor](./daba/meta.py)
* [Disambiguation interface](./daba/gdisamb.py)
* and some auxiliary scripts, see [daba package](./daba/) and [ad hoc
  dir](./daba/ad-hoc). 

### Dependencies

Daba is written in Python (currently requires Python 3.6 or higher) and uses
[wxPython](http://www.wxpython.org) (>= 4.1.0) cross-platform GUI library.

Daba is available for Windows, MacOS and Linux. Python and pip are
required for installation, see [instructions](./docs/INSTALL.md).


  

