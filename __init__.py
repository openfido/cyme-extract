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

import os, shutil, subprocess, sys, getopt
import pandas as pd

cache = "/usr/local/share/openfido" # additional path for downloaded modules
apiurl = "https://api.github.com"
rawurl = "https://raw.githubusercontent.com"
giturl = "https://github.com"
traceback_file = "/dev/stderr"

DEFAULT_OUTPUT=["zip", "csv", "png", "glm", "json"]

def main(inputs,outputs,options={}):
	INPUTNAME = inputs[0]
	OUTPUTDIR = os.path.abspath(os.path.dirname(outputs[0]))
	OUTPUTNAME = os.path.basename(outputs[0])
	CSVDIRNAME = INPUTNAME.split("/")[-1].split(".")[0]
	CSVDIR = f"/tmp/openfido/{CSVDIRNAME}"
	SRCDIR = os.getcwd()

	if os.path.exists(CSVDIR):
		os.system(f"rm -rf {CSVDIR}")
	os.system(f"mkdir -p {CSVDIR}")
	os.system(f"mkdir -p {OUTPUTDIR}")

	#
	# Load user configuration
	#
	print(f"OpenFIDO CYME-extract config settings:",flush=True)
	if os.path.exists("config.csv"):
		print(f"  Use settings from '{SRCDIR}/config.csv':",flush=True)
		config = pd.read_csv("config.csv", dtype=str,
			names=["name","value"],
			comment = "#",
			).set_index("name")
		settings = config["value"]
		INPUTTYPE = INPUTNAME.split(".")[1]
		TABLES = settings["TABLES"]
		EXTRACT = settings["EXTRACT"]
		TIMEZONE = "UTC"
		POSTPROCS = settings["POSTPROC"].split(" ")
		OUTPUTTYPE = OUTPUTNAME.split(".")[1]

	elif os.path.exists(f"{os.path.dirname(SRCDIR)}/config.csv"):
		print(f"  Use settings from '{os.path.dirname(SRCDIR)}/config.csv':",flush=True)
		config = pd.read_csv(f"{os.path.dirname(SRCDIR)}/config.csv", dtype=str,
			names=["name","value"],
			comment = "#",
			).set_index("name")
		settings = config["value"]
		INPUTTYPE = INPUTNAME.split(".")[1]
		TABLES = settings["TABLES"]
		EXTRACT = settings["EXTRACT"]
		TIMEZONE = "UTC"
		POSTPROCS = settings["POSTPROC"].split(" ")
		OUTPUTTYPE = OUTPUTNAME.split(".")[1]
	else:
		print(f"  No 'config.csv', using default settings:",flush=True)
		INPUTTYPE = INPUTNAME.split(".")[1]
		TABLES = "glm"
		EXTRACT = "all"
		TIMEZONE = "UTC"
		POSTPROCS = []
		OUTPUTTYPE = OUTPUTNAME.split(".")[1]

	if "ERROR_OUTPUT" in settings.keys() and os.path.exists(settings["ERROR_OUTPUT"]):
		os.remove(settings["ERROR_OUTPUT"])
	if "WARNING_OUTPUT" in settings.keys() and os.path.exists(settings["WARNING_OUTPUT"]):
		os.remove(settings["WARNING_OUTPUT"])
	if "GLM_OUTPUT" in settings.keys() and os.path.exists(settings["GLM_OUTPUT"]):
		os.remove(settings["GLM_OUTPUT"])
	if "VOL_OUTPUT" in settings.keys() and os.path.exists(settings["VOL_OUTPUT"]):
		os.remove(settings["VOL_OUTPUT"])
	if "PNG_OUTPUT" in settings.keys() and os.path.exists(settings["PNG_OUTPUT"]):
		os.remove(settings["PNG_OUTPUT"])

	PROCCONFIG = {
		"input_folder": SRCDIR,
		"output_folder": OUTPUTDIR,
		"postproc": POSTPROCS,
		"extract": EXTRACT,
		"outputs": OUTPUTTYPE,
		"inputs": INPUTTYPE,
		"tables": TABLES,
	}
	flags = []
	change_postprocs = False
	for option in options:
		if "=" in option:
			# Should we use command line to change converter configurations?
			opt_defined = option.split("=")
			if opt_defined[0].lower() in PROCCONFIG.keys():
				try:
					if opt_defined[0].lower() == "postproc":
						PROCCONFIG["postproc"] = opt_defined[1].split(" ")
					else:
						PROCCONFIG[opt_defined[0].lower()] = opt_defined[1]
				except:
					raise Exception(f"option {option} unexpected")
			else:
				print(f"option {option} unsupported")
		elif option[0] == '-':
			flags.append(option)
	flags = ' '.join(flags)

	print(f"  FILES = *.{PROCCONFIG['inputs']}",flush=True)
	print(f"  TABLES = {PROCCONFIG['tables']}",flush=True)
	print(f"  EXTRACT = {PROCCONFIG['extract']}",flush=True)
	print(f"  POSTPROC = {PROCCONFIG['postproc']}",flush=True)
	print(f"  OUTPUTS = {PROCCONFIG['outputs']}",flush=True)
	print(f"  output_folder = {PROCCONFIG['output_folder']}",flush=True)

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

	if "voltage_profile.py" in PROCCONFIG['postproc'] and "write_glm.py" in PROCCONFIG['postproc']:
		PROCCONFIG['postproc'].sort(key = 'voltage_profile.py'.__eq__)

	for process in (PROCCONFIG['postproc']):
		if process == process: 
			try:
				os.system(f"python3 {cache}/cyme-extract/postproc/{process} -i {PROCCONFIG['input_folder']} -o {PROCCONFIG['output_folder']} -c config.csv -d {CSVDIR} -g {OUTPUTNAME} {flags}")
			except:
				import traceback
				print(f"ERROR [mdb-cyme2glm]: {traceback.print_exc()}")
				sys.exit(15)
		else:
			print(f'cannot run postprocessing function "{process}"',flush=True)

	print(f"OpenFIDO CYME-extract Done. Moving config fiels to {PROCCONFIG['output_folder']}",flush=True)
	file_names = os.listdir(PROCCONFIG['input_folder'])
	for file_name in file_names:
		for EXT in DEFAULT_OUTPUT:
			if file_name.endswith(f".{EXT}"):
				if not os.path.exists(f"{PROCCONFIG['output_folder']}/{file_name}"):
					shutil.copy2(os.path.join(PROCCONFIG['input_folder'], file_name), PROCCONFIG['output_folder'])

	os.system(f"cd {CSVDIR} ; zip -q -R {PROCCONFIG['output_folder']}/{CSVDIRNAME}_tables.zip *.csv ./*.csv")
	os.system(f"rm -rf {CSVDIR}")
