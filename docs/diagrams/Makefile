# UML diagrams: DOT sources -> SVG (GitHub, docs) and PDF (LaTeX report).
# Needs Graphviz (`dot`). The class diagrams are generated from the code first.
PYTHON ?= ../../.venv/bin/python
SOURCES := use-cases-front-desk use-cases-management classes-domain-stays classes-domain-accounts classes-architecture

all: classes $(SOURCES:=.svg) $(SOURCES:=.pdf)

classes:
	$(PYTHON) class_diagrams.py

%.svg: %.dot actor.png
	dot -Tsvg $< -o $@
	$(PYTHON) class_diagrams.py --embed $@

%.pdf: %.dot actor.png
	dot -Tpdf $< -o $@

.PHONY: all classes
