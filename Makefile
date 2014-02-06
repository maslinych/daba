PROJECT=daba
VERSION := $(shell git describe --abbrev=4)
WINFILES = newmorph.py orthography.py grammar.py formats.py ntgloss.py gparser.pyw mparser.py gdisamb.pyw plugins/*.py metaprint.py wordparser.py dabased.py ad-hoc/daba2vert.py meta.py meta.xml __init__.py meta.cfg TextCtrlAutoComplete.py
RESOURCES = run/
FUNCPARSERLIB = /usr/lib/python2.7/site-packages/funcparserlib
PYTRIE = pytrie.py
DOC = doc/LICENSE doc/PyTrie-LICENSE doc/README.ru.txt doc/html/ doc/samples/* doc/meta.readme.txt


.PHONY: %.pyw

%.pyw: %.py
	cp $< $@

default: win-bundled

funcparserlib:
	cp -r $(FUNCPARSERLIB) .

pytrie:
	cp $(PYTRIE) .

docs:
	pushd doc
	make html
	mv _build/html .
	popd

win-bundled: $(WINFILES) $(RESOURCES) funcparserlib doc
	zip -r $(PROJECT)-$(VERSION).zip $(WINFILES) $(RESOURCES) $(DOC) funcparserlib/ pytrie.py -x run/*
