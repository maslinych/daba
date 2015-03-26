## Daba — Pattern-based morphemic analysis toolkit

Daba is a rule-based morphological analysis package. It's idea of
morphological processing is somewhat similar to the Porter stemmer
algorithm. Although the result of the analysis is not a plain stem,
but an annotated Gloss object that hold enough information for
morpheme-by-morpheme glossing known in linguistic typology and
anthropological linguistics as interlinear Glossed Text format.

Daba provides a set of cross-platform GUI and CLI tools required to
provide full cycle of corpus annotation followed by manual
disambiguation:

* morphological parser [GUI](./gparser.py) and [CLI](mparser.py)
  version
* [Metadata editor](./meta.py)
* [Disambiguation interface](./gdisamb.py)
* and some auxiliary scripts, see [ad hoc dir](./ad-hoc)

### Dependencies

* python 2.7
* [wxPython version 2.8](http://www.wxpython.org/download.php)
* [python module funcparserlib](https://pypi.python.org/pypi/funcparserlib/)
* [python module pytrie](https://pypi.python.org/pypi/pytrie)


  

