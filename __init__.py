#
# IMPORTANT NOTE: this script will automatically install needed tools only on system that use 'apt'
#
# Environment:
#
#   input_folder --> input folder where MDB files are placed
#   output_folder --> output folder where GLM files are placed
#   CSVDIR --> tmp folder where CSV files are placed
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
#     OUTPUTS,<ext1> <ext2> ... --> extensions to save (default "zip", "csv", "png", "glm", "json")
#

import os, shutil, subprocess
import pandas as pd

cache = "/usr/local/share/openfido" # additional path for downloaded modules
apiurl = "https://api.github.com"
rawurl = "https://raw.githubusercontent.com"
giturl = "https://github.com"
traceback_file = "/dev/stderr"

DEFAULT_OUTPUT=["zip", "csv", "png", "glm", "json"]

def main(inputs,outputs,options={}):
	print(77777)
	INPUTNAME = inputs[0]
	OUTPUTNAME = outputs[0]
	
	CSVDIRNAME = INPUTNAME.split(".")[0]
	CSVDIR = f"/tmp/openfido/{CSVDIRNAME}"
	SRCDIR = os.getcwd()
	OUTPUTDIR = f"{SRCDIR}/openfido_{CSVDIRNAME}_output"

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
	elif os.path.exists(f"{os.path.dirname(SRCDIR)}/config.csv"):
		print(f"Use settings from 'config.csv' in parent directory:")
		config = pd.read_csv(f"{os.path.dirname(SRCDIR)}/config.csv", dtype=str,
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
	else:
		print(f"No 'config.csv', using default settings:")
		INPUTTYPE = INPUTNAME.split(".")[1]
		TABLES = "glm"
		EXTRACT = "all"
		TIMEZONE = "UTC"
		POSTPROCS = []
		OUTPUTTYPE = OUTPUTNAME.split(".")[1]
	
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
		row_count = os.popen(f"wc -l {CSVDIR}/{csvname}.csv").read()
		if (int(row_count.strip().split(" ")[0]) == 1) and PROCCONFIG["extract"] != "all":
			os.remove(f"{CSVDIR}/{csvname}.csv")

	if not os.path.exists(PROCCONFIG['output_folder']):
		os.system(f"mkdir -p {PROCCONFIG['output_folder']}")

	for n in range(len(PROCCONFIG['postproc'])):
		process = PROCCONFIG['postproc'][n]
		try:
			raise Exception("test")
			os.system(f"python3 {cache}/cyme-extract/postproc/{process} -i {PROCCONFIG['input_folder']} -o {PROCCONFIG['output_folder']} -c config.csv -d {CSVDIR} -s")
		except:
			# raise Exception(f"{process} unavailable")
			import traceback
			print(f"ERROR [mdb-cyme2glm]: {traceback.print_exc()}")
			sys.exit(15)

	print(f"Moving config fiels to {PROCCONFIG['output_folder']}")
	file_names = os.listdir(PROCCONFIG['input_folder'])
	for file_name in file_names:
		for EXT in DEFAULT_OUTPUT:
			if file_name.endswith(f".{EXT}"):
				if not os.path.exists(f"{PROCCONFIG['output_folder']}/{file_name}"):
					shutil.copy2(os.path.join(PROCCONFIG['input_folder'], file_name), PROCCONFIG['output_folder'])

	# os.system(f"cd {CSVDIR} ; zip -q {PROCCONFIG['output_folder']}/{CSVDIRNAME}_database.zip *.csv")
	os.system(f"rm -rf {CSVDIR}")
