PROJECT=mparser
VERSION := $(shell git describe --abbrev=4)
WINFILES = newmorph.py orthography.py grammar.py ntgloss.py gparser.pyw parser.py disambiguator.py gdisamb.pyw
RESOURCES = bamana.bdi bamana.bgr
FUNCPARSERLIB = /usr/lib/python2.6/site-packages/funcparserlib

.PHONY: %.pyw

%.pyw: %.py
	cp $< $@

default: win-bundled

funcparserlib:
	cp -r $(FUNCPARSERLIB) .

win-bundled: $(WINFILES) $(RESOURCES) funcparserlib
	zip -r $(PROJECT)-$(VERSION).zip $(WINFILES) $(RESOURCES) funcparserlib/
