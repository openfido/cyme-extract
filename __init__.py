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
#
# This pipeline creates a CSV file name containing the file status of the input files.
#
# INPUTS
#
#   The list of files to be examined.
#
# OUTPUTS
#
#   The CSV file containing the file status information
#
#

import os
import pandas as pd
cache = "/usr/local/share/openfido" # additional path for downloaded modules
apiurl = "https://api.github.com"
rawurl = "https://raw.githubusercontent.com"
giturl = "https://github.com"
traceback_file = "/dev/stderr"

SRCDIR = os.getcwd()
OUTPUTDIR = f"{SRCDIR}/output"
DEFAULT_OUTPUT="zip csv png glm json"

def main(inputs,outputs,options={}):
	
	print("SRCDIR: ", SRCDIR)
	
	INPUTNAME = inputs[0]
	OUTPUTNAME = outputs[0]

	CSVDIRNAME = INPUTNAME.split(".")[0]
	CSVDIR = f"/tmp/openfido/{CSVDIRNAME}"
	if os.path.exists(CSVDIR):
		os.system(f"rm -rf {CSVDIR}")
	os.system(f"mkdir -p {CSVDIR}")
	print("CSVDIR: ", CSVDIR)

	#
	# Load user configuration
	#
	if os.path.exists("config.csv"):
		config = pd.read_csv("config.csv", dtype=str,
			names=["name","value"],
			comment = "#",
			).set_index("name")
		settings = config["value"]
		INPUTTYPE = INPUTNAME.split(".")[1]
		TABLES = settings["TABLES"]
		EXTRACT = settings["EXTRACT"]
		TIMEZONE = "UTC"
		POSTPROC = settings["POSTPROC"].tolist()
		OUTPUTTYPE = OUTPUTNAME.split(".")[1]
		print(POSTPROC)
		print(f"OpenFIDO config settings")
		print(f"FILES = *.{INPUTTYPE}")
		print(f"TABLES = {TABLES}")
		print(f"EXTRACT = {EXTRACT}")
		print(f"POSTPROC = {POSTPROC}")
		print(f"OUTPUTS = {OUTPUTTYPE}")
	else:
		print(f"No 'config.csv', using default settings:")
		INPUTTYPE = INPUTNAME.split(".")[1]
		TABLES = "glm"
		EXTRACT = "all"
		TIMEZONE = "UTC"
		POSTPROC = ""
		OUTPUTTYPE = OUTPUTNAME.split(".")[1]
		print(POSTPROC)
		print(f"OpenFIDO config settings")
		print(f"FILES = *.{INPUTTYPE}")
		print(f"TABLES = {TABLES}")
		print(f"EXTRACT = {EXTRACT}")
		print(f"POSTPROC = {POSTPROC}")
		print(f"OUTPUTS = {OUTPUTTYPE}")


	result = os.popen(f"python3 {cache}/cyme-extract/postproc/write_glm.py --cyme-tables").read()
	tables = result.split()

	for table in tables:
		csvname = table[3:].lower()
		os.system(f"mdb-export {INPUTNAME} {table} > {CSVDIR}/{csvname}.csv")

	if os.path.exists(OUTPUTDIR):
		os.system(f"rm -rf {OUTPUTDIR}")
	os.system(f"mkdir -p {OUTPUTDIR}")

	os.system(f"python3 {cache}/cyme-extract/postproc/write_glm.py -i {SRCDIR} -o {OUTPUTDIR} -c config.csv -d {CSVDIR}")

































