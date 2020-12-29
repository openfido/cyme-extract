#!/bin/bash
#
# IMPORTANT NOTE: this script will automatically install needed tools only on system that use 'apt'
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
#     POSTPROC,<file1> <file2> ... --> run postprocessing routines (default none)
#     OUTPUTS,<ext1> <ext2> ... --> extensions to save (default "zip csv json")
#

# current version of pipeline (increment this when a major change in functionality is deployed)
VERSION=0  

# nounset: undefined variable outputs error message, and forces an exit
set -u

# errexit: abort script at first error
set -e

# print command to stderr before executing it:
set -x

# generate absolute path from relative path
function abspath() {
    # $1     : relative filename
    # return : absolute path
    if [ -d "$1" ]; then
        # dir
        (cd "$1"; pwd)
    elif [ -f "$1" ]; then
        # file
        if [[ $1 = /* ]]; then
            echo "$1"
        elif [[ $1 == */* ]]; then
            echo "$(cd "${1%/*}"; pwd)/${1##*/}"
        else
            echo "$(pwd)/$1"
        fi
    fi
}

# path to executables
SRCDIR=$(abspath ${0%/*})

# startup notice
echo "Starting $0 at $(date)..."

# display environment information
echo "Environment settings:"
echo "  OPENFIDO_INPUT = $OPENFIDO_INPUT"
echo "  OPENFIDO_OUTPUT = $OPENFIDO_OUTPUT"

# install mdbtools if missing
if [ -z "$(which mdb-export)" ]; then
	echo "Installing mdbtools"
	apt update -qq
	DEBIAN_FRONTEND=noninteractive apt-get install -yqq --no-install-recommends tzdata
	apt install mdbtools zip -yqq
fi

# work in new temporary directory
TMP=/tmp/openfido-$$
rm -rf $TMP
mkdir -p "$TMP"
OLDWD=$PWD
cd "$TMP"

# copy input files to workdir
echo "Copying files from $OPENFIDO_INPUT..."
for FILE in $(ls -1 $OPENFIDO_INPUT/*); do
	echo "  $FILE ($(wc -c $FILE | awk '{print $1}') bytes)"
	cp -R "$FILE" .
done

# process config file
if [ -f "config.csv" ]; then
	FILES=$(grep ^FILES, config.csv | cut -f2 -d,)
	TABLES=$(grep ^TABLES, config.csv | cut -f2 -d,)
	EXTRACT=$(grep ^EXTRACT, config.csv | cut -f2 -d,)
	TIMEZONE=$(grep ^TIMEZONE, config.csv | cut -f2 -d,)
	POSTPROC=$(grep ^POSTPROC, config.csv | cut -f2 -d,)
	OUTPUTS=$(grep ^OUTPUTS, config.csv | cut -f2 -d,)
	echo "Config settings:"
	echo "  FILES = ${FILES:-}"
	echo "  TABLES = ${TABLES:-}"
	echo "  EXTRACT = ${EXTRACT:-}"
	echo "  TIMEZONE = ${TIMEZONE:-}"
	echo "  POSTPROC = ${POSTPROC:-}"
	echo "  OUTPUTS = ${OUTPUTS:-}"
else
	echo "No 'config.csv', using default settings:"
	echo "  FILES = *.mdb"
	echo "  TABLES = *"
	echo "  EXTRACT = all"
	echo "  TIMEZONE = UTC"
	echo "  POSTPROC = "
	echo "  OUTPUTS = zip csv json"
fi

# install python3 if missing
if [ "${POSTPROC:-}" != "" -a "$(which python3)" == "" ]; then
	apt install python3 -yqq
fi

# install tzdata if missing and needed
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

# process the input files
INDEX=index.csv
echo "database,table,csvname,size,rows" > "$INDEX"
for DATABASE in $(ls -1 *.mdb | grep ${FILES:-.\*}); do
	CSVDIR=${DATABASE%.*}
	mkdir -p "$CSVDIR"
	for TABLE in ${TABLES:-$(mdb-tables "$DATABASE")}; do
		CSV=$(echo $TABLE | cut -c4- | tr A-Z a-z).csv
		mdb-export "$DATABASE" "$TABLE" > "$CSVDIR/$CSV"
		SIZE=$(wc -c $CSVDIR/$CSV | awk '{print $1}' )
		ROWS=$(wc -l $CSVDIR/$CSV | awk '{print $1}' )
		if [ "$ROWS" -gt 1 -o "${EXTRACT:-all}" = "all" ]; then
			echo "$DATABASE,$TABLE,$CSV,$SIZE,$(($ROWS-1))" >> "$INDEX"
		else
			rm "$CSVDIR/$CSV"
		fi
	done
	if [ "${POSTPROC:-}" != "" ]; then
		for PROC in ${POSTPROC}; do
			(cd $CSVDIR ; $SRCDIR/postproc/$PROC)
		done
	fi
	(cd "$CSVDIR" ; zip -q "../$CSVDIR.zip" *.csv )
	rm -rf "$CSVDIR"
done

# output version info
echo version > version.csv
echo $VERSION >> version.csv

# copy results to output
echo "Moving results to $OPENFIDO_OUTPUT..."
for EXT in ${OUTPUTS:-zip csv json}; do
	for FILE in $(find . -name '*.'$EXT -print); do
		echo "  $FILE ($(wc -c $FILE | awk '{print $1}') bytes)"
		mv $FILE "$OPENFIDO_OUTPUT"
	done
done

# cleanup
cd $OLDWD
rm -rf $TMP

echo "Completed $0 at $(date)"

