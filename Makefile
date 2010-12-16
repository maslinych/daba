PROJECT=mparser
VERSION := $(shell git describe --abbrev=4)
WINFILES = newmorph.py orthgraphy.py grammar.py ntgloss.py gparser.pyw
RESOURCES = bamana.bdi bamana.bgr

%.pyw: %.py
	cp $< $@

win-bundled:
	zip -r $(PROJECT)-$(VERSION).zip $(WINFILES) $(RESOURCES)
