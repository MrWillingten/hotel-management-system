#!/bin/sh
# Build the Checkpoint 1 PDF: ./build.sh "Student Name" [python with weasyprint]
# Needs Graphviz (dot) and WeasyPrint (pip install weasyprint).
set -eu
cd "$(dirname "$0")"
STUDENT="${1:?usage: ./build.sh \"Student Name\"}"
PY="${2:-python3}"
dot -Tpng -Gdpi=200 erd.dot -o erd.png
sed "s/{{STUDENT}}/$STUDENT/g" cp1.html > .cp1-named.html
"$PY" -c "import weasyprint; weasyprint.HTML('.cp1-named.html').write_pdf('CP1-Analysis.pdf')"
rm .cp1-named.html
echo "wrote CP1-Analysis.pdf"
