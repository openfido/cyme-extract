#!/bin/bash

# nounset: undefined variable outputs error message, and forces an exit
set -u
# errexit: abort script at first error
set -e
# print command to stdout before executing it:
set -x

echo "OPENFIDO_INPUT = $OPENFIDO_INPUT"
echo "OPENFIDO_OUTPUT = $OPENFIDO_OUTPUT"

if [ -z "$(which mdb-export)" ]; then
	echo "Installing mdbtools"
	apt update -qq
	DEBIAN_FRONTEND=noninteractive apt-get install -yqq --no-install-recommends tzdata
	apt install mdbtools -yqq
fi

TMP=/tmp/openfido-$$
echo "Creating working direction $TMP"
mkdir -p $TMP
cd $TMP

echo "Copying input files to working directory"
cp -r $OPENFIDO_INPUT/* .

INDEX=index.csv
echo "database,table,csvname,size,rows" > $INDEX
for DATABASE in $(ls -1 *.mdb); do
	CSVDIR=${DATABASE/.mdb/}
	mkdir -p $CSVDIR
	for TABLE in $(mdb-tables $DATABASE); do
		CSV=$(echo ${TABLE/CYM/} | tr A-Z a-z).csv
		mdb-export "$DATABASE" "$TABLE" > "$CSVDIR/$CSV"
		SIZE=$(echo $(wc -c $CSVDIR/$CSV) | cut -f1 -d' ' )
		ROWS=$(echo $(wc -l $CSVDIR/$CSV) | cut -f1 -d' ' )
		echo "$DATABASE,$TABLE,$CSV,$SIZE,$(($ROWS-1))" >> $INDEX
	done
done

mv $TMP/* $OPENFIDO_OUTPUT 
