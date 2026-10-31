#!/bin/sh
# Build the Checkpoint 2 PDF: ./build.sh "Student Name" [python with weasyprint]
# Needs WeasyPrint (pip install weasyprint).
set -eu
cd "$(dirname "$0")"
STUDENT="${1:?usage: ./build.sh \"Student Name\"}"
PY="${2:-python3}"

sed "s/{{STUDENT}}/$STUDENT/g" cp2.html > .cp2-named.html
"$PY" -c "import weasyprint; weasyprint.HTML('.cp2-named.html').write_pdf('CP2-Procedural-Prototype.pdf')"
rm .cp2-named.html
echo "wrote CP2-Procedural-Prototype.pdf"
