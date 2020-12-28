#!/bin/bash
#
# Environment:
#
#   OPENFIDO_INPUT --> input folder when MDB files are placed
#   OPENFIDO_OUTPUT --> output folder when CSV files are placed
#
# Special files:
#
#   config.csv -> run configuration
#
#     FILES=<grep-pattern> --> restricts the names of the database to extract
#     TABLES=<table-list> --> extract only the listed tables
#     EXTRACT=[all|non-empty] --> extracts all or only non-empty tables
#     

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

if [ -f "config.csv" ]; then
	FILES=$(grep ^FILES= config.csv | cut -f2 -d=)
	TABLES=$(grep ^TABLES= config.csv | cut -f2 -d=)
	EXTRACT=$(grep ^EXTRACT= config.csv | cut -f2 -d=)
fi

INDEX=index.csv
echo "database,table,csvname,size,rows" > $INDEX
for DATABASE in $(ls -1 *.mdb | grep ${FILES:-.\*}); do
	CSVDIR=${DATABASE/.mdb/}
	mkdir -p $CSVDIR
	for TABLE in ${TABLES:-$(mdb-tables $DATABASE)}; do
		CSV=$(echo ${TABLE/CYM/} | tr A-Z a-z).csv
		mdb-export "$DATABASE" "$TABLE" > "$CSVDIR/$CSV"
		SIZE=$(echo $(wc -c $CSVDIR/$CSV) | cut -f1 -d' ' )
		ROWS=$(echo $(wc -l $CSVDIR/$CSV) | cut -f1 -d' ' )
		if [ $ROWS -gt 1 -o "${EXTRACT:-non-empty}" == "all" ]; then
			echo "$DATABASE,$TABLE,$CSV,$SIZE,$(($ROWS-1))" >> $INDEX
		else
			rm "$CSVDIR/$CSV"
		fi
	done
done

mv $TMP/* $OPENFIDO_OUTPUT 
