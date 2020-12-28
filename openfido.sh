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
#     FILES,<grep-pattern> --> restricts the names of the database to extract (default *.mdb)
#     TABLES,<table-list> --> extract only the listed tables (default *)
#     EXTRACT,[all|non-empty] --> extracts all or only non-empty tables (default all)
#     TIMEZONE,<country>/<city> --> changes localtime to use specified timezone (default UTC)
#

VERSION=0  

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
mkdir -p "$TMP"
cd "$TMP"

echo "Copying input files to working directory"
cp -r "$OPENFIDO_INPUT"/* .

if [ -f "config.csv" ]; then
	FILES=$(grep ^FILES, config.csv | cut -f2 -d,)
	TABLES=$(grep ^TABLES, config.csv | cut -f2 -d,)
	EXTRACT=$(grep ^EXTRACT, config.csv | cut -f2 -d,)
	TIMEZONE=$(grep ^TIMEZONE, config.csv | cut -f2 -d,)
fi

if [ -f "/usr/share/zoneinfo/${TIMEZONE:-}" ]; then
	export DEBIAN_FRONTEND=noninteractive
	ln -sf "/usr/share/zoneinfo/$TIMEZONE" "/etc/localtime"
	apt-get install tzdata -yqq
	dpkg-reconfigure --frontend noninteractive tzdata
elif [ ! -z "${TIMEZONE:-}" ]; then
	export DEBIAN_FRONTEND=noninteractive
	apt-get install tzdata -yqq
	echo "WARNING [config.csv]: TIMEZONE=$TIMEZONE is not valid (/usr/share/zoneinfo/$TIMEZONE not found)"
	echo "  See 'timezones.csv' for a list of valid timezones"
	echo "timezone" > timezones.csv
	for TZDATA in $(find -L /usr/share/zoneinfo/posix -name '[A-Z]*' -print); do
		echo ${TZDATA/\/usr\/share\/zoneinfo\/posix\//} >> timezones.csv
	done
fi

INDEX=index.csv
echo "database,table,csvname,size,rows" > "$INDEX"
for DATABASE in $(ls -1 *.mdb | grep ${FILES:-.\*}); do
	CSVDIR=${DATABASE%.*}
	mkdir -p "$CSVDIR"
	for TABLE in ${TABLES:-$(mdb-tables "$DATABASE")}; do
		CSV=$(echo ${TABLE/CYM/} | tr A-Z a-z).csv
		mdb-export "$DATABASE" "$TABLE" > "$CSVDIR/$CSV"
		SIZE=$(echo $(wc -c $CSVDIR/$CSV) | cut -f1 -d' ' )
		ROWS=$(echo $(wc -l $CSVDIR/$CSV) | cut -f1 -d' ' )
		if [ "$ROWS" -gt 1 -o "${EXTRACT:-all}" == "all" ]; then
			echo "$DATABASE,$TABLE,$CSV,$SIZE,$(($ROWS-1))" >> "$INDEX"
		else
			rm "$CSVDIR/$CSV"
		fi
	done
done

echo version > version.csv
echo $VERSION >> version.csv

mv "$TMP"/* "$OPENFIDO_OUTPUT" 
