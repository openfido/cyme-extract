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

import os, shutil
import pandas as pd

cache = "/usr/local/share/openfido" # additional path for downloaded modules
apiurl = "https://api.github.com"
rawurl = "https://raw.githubusercontent.com"
giturl = "https://github.com"
traceback_file = "/dev/stderr"

SRCDIR = os.getcwd()
OUTPUTDIR = f"{SRCDIR}/output"
DEFAULT_OUTPUT=["zip", "csv", "png", "glm", "json"]

def main(inputs,outputs,options={}):
	
	INPUTNAME = inputs[0]
	OUTPUTNAME = outputs[0]

	CSVDIRNAME = INPUTNAME.split(".")[0]
	CSVDIR = f"/tmp/openfido/{CSVDIRNAME}"
	if os.path.exists(CSVDIR):
		os.system(f"rm -rf {CSVDIR}")
	os.system(f"mkdir -p {CSVDIR}")

	#
	# Load user configuration
	#
	if os.path.exists("config.csv"):
		print(f"Use settings from 'config.csv':")
		config = pd.read_csv("config.csv", dtype=str,
			names=["name","value"],
			comment = "#",
			).set_index("name")
		settings = config["value"]
		INPUTTYPE = INPUTNAME.split(".")[1]
		TABLES = settings["TABLES"]
		EXTRACT = settings["EXTRACT"]
		TIMEZONE = "UTC"
		POSTPROCS = settings["POSTPROC"].tolist()
		OUTPUTTYPE = OUTPUTNAME.split(".")[1]
		print(POSTPROCS)
	else:
		print(f"No 'config.csv', using default settings:")
		INPUTTYPE = INPUTNAME.split(".")[1]
		TABLES = "glm"
		EXTRACT = "all"
		TIMEZONE = "UTC"
		POSTPROCS = []
		OUTPUTTYPE = OUTPUTNAME.split(".")[1]
		print(POSTPROCS)
	
	PROCCONFIG = {
		"input_folder": SRCDIR,
		"output_folder": OUTPUTDIR,
		"postproc": POSTPROCS,
		"extract": EXTRACT,
		"outputs": OUTPUTTYPE,
		"inputs": INPUTTYPE,
		"tables": TABLES,
	}

	for option in options:
		if "=" in option:
			opt_defined = option.split("=")
			if opt_defined[0] in PROCCONFIG.keys():
				if opt_defined[0] == "postproc":
					PROCCONFIG[opt_defined[0]] = [opt_defined[1]]
				else:
					try:
						PROCCONFIG[opt_defined[0]] = opt_defined[1]
					except:
						raise Exception(f"option {option} unexpected")

	print("PROCCONFIG new: ", PROCCONFIG)

	print(f"OpenFIDO config settings")
	print(f"FILES = *.{PROCCONFIG['inputs']}")
	print(f"TABLES = {PROCCONFIG['tables']}")
	print(f"EXTRACT = {PROCCONFIG['extract']}")
	print(f"POSTPROC = {PROCCONFIG['postproc']}")
	print(f"OUTPUTS = {PROCCONFIG['outputs']}")


	result = os.popen(f"python3 {cache}/cyme-extract/postproc/write_glm.py --cyme-tables").read()
	tables = result.split()

	for table in tables:
		csvname = table[3:].lower()
		os.system(f"mdb-export {PROCCONFIG['input_folder']}/{INPUTNAME} {table} > {CSVDIR}/{csvname}.csv")

	# if os.path.exists(OUTPUTDIR):
	# 	os.system(f"rm -rf {OUTPUTDIR}")
	# os.system(f"mkdir -p {OUTPUTDIR}")
	for n in range(len(PROCCONFIG['postproc'])):
		process = PROCCONFIG['postproc'][n]
		print("init process: ", process)
		try:
			os.system(f"python3 {cache}/cyme-extract/postproc/{process} -i {PROCCONFIG['output_folder']} -o {PROCCONFIG['output_folder']} -c config.csv -d {CSVDIR}")
		except:
			raise Exception(f"{process} unavailable")

	print(f"Moving config fiels to {PROCCONFIG['output_folder']}")
	file_names = os.listdir(PROCCONFIG['output_folder'])
	for file_name in file_names:
		for EXT in DEFAULT_OUTPUT:
			if file_name.endswith(f".{EXT}"):
				if not os.path.exists(f"{PROCCONFIG['output_folder']}/{file_name}"):
					shutil.copy2(os.path.join(PROCCONFIG['output_folder'], file_name), PROCCONFIG['output_folder'])

