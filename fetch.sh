#!/bin/sh
# Downloads the current sources into src/ (JMdict with all languages, KANJIDIC2, Kanjium accents).
set -eu
cd "$(dirname "$0")"
mkdir -p src
curl -sSfL -o src/JMdict.gz http://ftp.edrdg.org/pub/Nihongo/JMdict.gz
curl -sSfL -o src/kanjidic2.xml.gz http://ftp.edrdg.org/pub/Nihongo/kanjidic2.xml.gz
curl -sSfL -o src/accents.txt \
  https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw/accents.txt
ls -l src
