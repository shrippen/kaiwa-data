#!/bin/sh
# Builds dist/kaiwa-data-<version>.tar.bz2 from the sources in src/ (see fetch.sh) and writes
# its SHA-256 and size next to it. Kaiwa pins both in kaiwa_speech::download.
#   ./package.sh 0.2.0
set -eu
cd "$(dirname "$0")"
version=${1:?usage: ./package.sh <version>}
name=kaiwa-data-$version
rm -rf "dist/$name"
mkdir -p "dist/$name"
python3 build.py --jmdict src/JMdict.gz --jmnedict src/JMnedict.xml.gz \
  --kanjidic src/kanjidic2.xml.gz --accents src/accents.txt --tanos src/tanos \
  --out "dist/$name/kaiwa-dict.sqlite" --version "$version"
cp NOTICE LICENSE-DATA "dist/$name/"
# Same input, same archive: fixed order, owner and time.
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime=@0 \
  -C dist -cf - "$name" | bzip2 -9 > "dist/$name.tar.bz2"
(cd dist && sha256sum "$name.tar.bz2" > "$name.tar.bz2.sha256")
stat -c '%s bytes' "dist/$name.tar.bz2"
cat "dist/$name.tar.bz2.sha256"
