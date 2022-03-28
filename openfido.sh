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

# defaults
DEFAULT_OUTPUT="zip csv png glm json"

# error handling
EXECNAME=$0
TMP=/tmp/openfido-$$
OLDWD=$PWD
LINENO="?"
trap 'onexit $0 $LINENO $?' EXIT
onexit()
{
	cd $OLDWD
	rm -rf $TMP
	if [ $3 -ne 0 ]; then
		echo "*** ERROR $3 ***"
		grep -v '^+' $OPENFIDO_OUTPUT/stderr
		echo "  $1($2): see $OPENFIDO_OUTPUT/stderr output for details"
	fi
	echo "Completed $1 at $(date)"
	exit $3
}

# nounset: undefined variable outputs error message, and forces an exit
set -u

# errexit: abort script at first error
set -e

# print command to stderr before executing it:
set -x

# path to postproc folder
if [ "$0" = "openfido.sh" ]; then
	SRCDIR=$PWD
else
	SRCDIR=$(cd $(echo "$0" | sed "s/$(basename $0)\$//") ; pwd )
fi

# startup notice
echo "Starting $0 at $(date)..."

# display environment information
echo "Environment settings:"
echo "  OPENFIDO_INPUT = $OPENFIDO_INPUT"
echo "  OPENFIDO_OUTPUT = $OPENFIDO_OUTPUT"

# work in new temporary directory
rm -rf $TMP
mkdir -p "$TMP"
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
	POSTPROC=$(grep ^POSTPROC, config.csv | cut -f2 -d, | tr '\n' ' ')
	OUTPUTS=$(grep ^OUTPUTS, config.csv | cut -f2 -d,)
	echo "Config settings:"
	echo "  FILES = ${FILES:-*.mdb}"
	echo "  TABLES = ${TABLES:-*}"
	echo "  EXTRACT = ${EXTRACT:-all}"
	echo "  TIMEZONE = ${TIMEZONE:-UTC}"
	echo "  POSTPROC = ${POSTPROC:-}"
	echo "  OUTPUTS = ${OUTPUTS:-${DEFAULT_OUTPUT}}"
else
	echo "No 'config.csv', using default settings:"
	echo "  FILES = *.mdb"
	echo "  TABLES = all"
	echo "  EXTRACT = all"
	echo "  TIMEZONE = UTC"
	echo "  POSTPROC = "
	echo "  OUTPUTS = ${DEFAULT_OUTPUT}"
fi

# get list of required tables
if [ "$TABLES" = "glm" ]; then
	TABLES=$($SRCDIR/postproc/write_glm.py --cyme-tables)
elif [ "$TABLES" = "all" ]; then
	TABLES=$(mdb-tables "$DATABASE")
fi

# process the input files
INDEX=index.csv
echo "database,table,csvname,size,rows" > "$INDEX"
for DATABASE in $(ls -1 *.mdb | grep ${FILES:-.\*}); do
	CSVDIR=$PWD/${DATABASE%.*}
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
		for PROC in ${make $SRCDIR/postproc/Makefile $POSTPROC | tr '\n' ' '}; do
			( $SRCDIR/postproc/$PROC -i${OPENFIDO_INPUT} -o${OPENFIDO_OUTPUT} -c${OPENFIDO_INPUT}/config.csv -d${CSVDIR} </dev/null )
		done
	fi
	(cd "$CSVDIR" ; zip -q "${OPENFIDO_OUTPUT}/${DATABASE%.*}.zip" *.csv )
	rm -rf "$CSVDIR"
done

# output version info
echo version,$VERSION >version.csv

# copy results to output
echo "Moving results to $OPENFIDO_OUTPUT..."
for EXT in ${OUTPUTS:-${DEFAULT_OUTPUT}}; do
	for FILE in $(find . -name '*.'$EXT -print); do
		echo "  $FILE ($(wc -c $FILE | awk '{print $1}') bytes)"
		mv $FILE "$OPENFIDO_OUTPUT"
	done
done
