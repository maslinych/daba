PROJECT=mparser
VERSION := $(shell git describe --abbrev=4)
WINFILES = newmorph.py orthography.py grammar.py dictparser.py formats.py ntgloss.py gparser.pyw mparser.py gdisamb.pyw 
RESOURCES = run/
FUNCPARSERLIB = /usr/lib/python2.6/site-packages/funcparserlib
#PYTRIE = /usr/lib/python2.6/site-packages/pytrie.py


.PHONY: %.pyw

%.pyw: %.py
	cp $< $@

default: win-bundled

funcparserlib:
	cp -r $(FUNCPARSERLIB) .

pytrie:
	cp $(PYTRIE) .

win-bundled: $(WINFILES) $(RESOURCES) funcparserlib 
	zip -r $(PROJECT)-$(VERSION).zip $(WINFILES) $(RESOURCES) funcparserlib/ pytrie.py
