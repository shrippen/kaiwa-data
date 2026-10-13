#!/bin/sh
# Downloads the sources into src/: JMdict with all languages, JMnedict, KANJIDIC2, Kanjium accents
# (current versions) and the JLPT word lists of tanos.co.uk from fixed snapshots in the Internet
# Archive (the site's CC BY licence is confirmed there, Kaiwa L-09; the snapshots keep the build
# reproducible).
set -eu
cd "$(dirname "$0")"
mkdir -p src/tanos
curl -sSfL -o src/JMdict.gz http://ftp.edrdg.org/pub/Nihongo/JMdict.gz
curl -sSfL -o src/JMnedict.xml.gz http://ftp.edrdg.org/pub/Nihongo/JMnedict.xml.gz
curl -sSfL -o src/kanjidic2.xml.gz http://ftp.edrdg.org/pub/Nihongo/kanjidic2.xml.gz
curl -sSfL -o src/accents.txt \
  https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw/accents.txt
for snap in 5:20200728231522 4:20200629172633 3:20200629172607 2:20200629172602 1:20200218172500; do
  level=${snap%%:*}
  curl -sSfL --retry 3 -o "src/tanos/n$level.html" \
    "https://web.archive.org/web/${snap#*:}id_/http://www.tanos.co.uk:80/jlpt/jlpt$level/vocab/"
done
ls -l src src/tanos
