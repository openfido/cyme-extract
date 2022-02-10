#!/usr/bin/python3
"""OpenFIDO write_glm post-processor script (version: develop)
Syntax:
	host% python3 -m write_glm.py -i|--input INPUTDIR -o|--output OUTPUTDIR -d|--data DATADIR [-c|--config [CONFIGCSV]] 
	[-h|--help] [-t|--cyme-tables] [-s|--single] [-n|--network ID]
Concept of Operation
--------------------
Files are processed in the local folder, which must contain the required CSV files list in the `cyme_tables_required` 
global variable. 
Operation of this script is controlled by the file `{INPUTDIR}/config.csv`:
	TABLES,glm
	EXTRACT,non-empty
	POSTPROC,write_glm.py
	GLM_NOMINAL_VOLTAGE,2.40178 kV
	GLM_NETWORK_PREFIX,IEEE13_
	GLM_INCLUDE,config.glm
	GLM_MODIFY,modify.csv
	GLM_DEFINE,SOLUTIONDUMP=yes
	GLM_ASSUMPTIONS,include
All output is written to the parent folder.  Currently the following files are generated, depending on the
settings in control file:
  - `{OUTPUTDIR}/{MDBNAME}_{NETWORKID}.glm`
  - `{OUTPUTDIR}/{MDBNAME}_{NETWORKID}_assumptions.glm`
  - `{OUTPUTDIR}/{MDBNAME}_{NETWORKID}_assumptions.glm`
  - `{OUTPUTDIR}/{MDBNAME}_{NETWORKID}_assumptions.csv`
"""

app_version = 0

import sys, os
import getopt
import subprocess
import glob
import datetime as dt
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import math
from math import sqrt, cos, sin, pi
import re
import hashlib
import csv
import pprint
pp = pprint.PrettyPrinter(indent=4,compact=True)
import traceback
from copy import copy
import numpy as np

#
# Required tables to operate properly
# 
cyme_tables_required = [
	"CYMNETWORK","CYMHEADNODE","CYMNODE","CYMSECTION","CYMSECTIONDEVICE",
	"CYMOVERHEADBYPHASE","CYMOVERHEADLINEUNBALANCED","CYMEQCONDUCTOR",
	"CYMEQGEOMETRICALARRANGEMENT","CYMEQOVERHEADLINEUNBALANCED","CYMEQFUSE",
	"CYMSWITCH","CYMCUSTOMERLOAD","CYMLOAD","CYMSHUNTCAPACITOR","CYMFUSE",
	"CYMTRANSFORMER","CYMEQTRANSFORMER","CYMREGULATOR","CYMEQREGULATOR",
	"CYMOVERHEADLINE","CYMUNDERGROUNDLINE","CYMNODETAG","CYMEQCABLE",
	"CYMANTIISLANDING","CYMARCFLASHNODE","CYMAUTOTAPCHANGINGEXTST","CYMBACKGROUNDMAP",
	"CYMBREAKER","CYMBUSWAY","CYMCAPACITOREXTLTD","CYMCONSUMERCLASS",
	"CYMCTYPEFILTER","CYMDCLINK","CYMTRANSFORMERBYPHASE","CYMRECLOSER","CYMEQOVERHEADLINE",
	"CYMSOURCE","CYMEQSHUNTCAPACITOR"]

#
# Argument parsing
#
config = {
	"input" : "/",
	"output" : "/",
	"from" : {},
	"type" : {},
	"options" : {
		"config" : "specify config.csv",
		"cyme-tables" : "get required CYME tables",
	},
}
input_folder = None
output_folder = None
data_folder = None
config_file = None
equipment_file = None
network_select = None
single_file = False
opts, args = getopt.getopt(sys.argv[1:],"hc:i:o:d:tsn:e:",["help","config=","input=","output=","data=","cyme-tables","single","network ID"])

def help(exit_code=None,details=False):
	print("Syntax: python3 -m write_glm.py -i|--input DIR -o|--output DIR -d|--data DIR [-h|--help] [-t|--cyme-tables] [-c|--config CSV] [-e|--equipment DIR] [-s|--single] [-n|--network_ID ID]")
	if details:
		print(globals()[__name__].__doc__)
	if type(exit_code) is int:
		exit(exit_code)

if not opts : 
	help(1)

for opt, arg in opts:
	if opt in ("-h","--help"):
		help(0,details=True)
	elif opt in ("-c","--config"):
		if arg:
			config_file = arg.strip()
		else:
			print(config)
	elif opt in ("-t","--cyme-tables"):
		print(" ".join(cyme_tables_required))
		sys.exit(0)
	elif opt in ("-i", "--input"):
		input_folder = arg.strip()
	elif opt in ("-o", "--output"):
		output_folder = arg.strip()
	elif opt in ("-d", "--data"):
		data_folder = arg.strip()
	elif opt in ("-s", "--single"):
		single_file = True
	elif opt in ("-n", "--network_ID"):
		# only extract the selected network
		network_select = arg.strip()
	elif opt in ("-e", "--equipment"):
		equipment_file = arg.strip()
	else:
		error(f"{opt}={arg} is not a valid option");
if input_folder == None:
	raise Exception("input_folder must be specified using '-i|--input DIR' option")
if output_folder == None:
	raise Exception("output_folder must be specified using '-o|--OUTPUT DIR' option")
if data_folder == None:
	raise Exception("data_folder must be specified using '-d|--data DIR' option")
if config_file == None:
	config_file = f"{input_folder}/config.csv"

#
# Application information
#
app_command = os.path.abspath(sys.argv[0])
app_workdir = os.getenv("PWD")
app_path = "/"+"/".join(app_command.split("/")[0:-1])

#
# Git information
#
# TODO: change this to use gitpython module
#
def command(cmd,lang="utf-8"):
	return subprocess.run(cmd.split(),stdout=subprocess.PIPE).stdout.decode(lang).strip()
os.chdir(app_path)
git_project = command("git config --local remote.origin.url")
git_commit = command("git rev-parse HEAD")
git_branch = command("git rev-parse --abbrev-ref HEAD")
os.chdir(app_workdir)

#
# CYME model information
#
cyme_mdbname = data_folder.split("/")[-1]
default_cyme_extractor = "5020"

#
# Warning/error handling
#
warning_count = 0
def warning(*args):
	global warning_count
	warning_count += 1
	if settings["GLM_WARNINGS"] == "stdout":
		print(f"*** WARNING {warning_count} ***")
		print(" ","\n  ".join(args))
	elif settings["GLM_WARNINGS"] == "stderr":
		print(f"*** WARNING {warning_count} ***",file=sys.stderr)
		print(" ","\n  ".join(args),file=sys.stderr)
	else:
		raise Exception("\n".join(args))

error_count = 0
def error(*args):
	global error_count
	error_count += 1
	if settings["GLM_ERRORS"] == "stdout":
		print(f"*** ERROR {error_count} ***")
		print(" ","\n  ".join(args))
	elif settings["GLM_ERRORS"] == "stderr":
		print(f"*** ERROR {error_count} ***",file=sys.stderr)
		print(" ","\n  ".join(args),file=sys.stderr)
	else:
		raise Exception("\n".join(args))

def format_exception(errmsg,ref=None,data=None):
	tb = str(traceback.format_exc().replace('\n','\n  '))
	dd = str(pp.pformat(data).replace('\n','\n  '))
	return "\n  " + tb + "'" + ref  + "' =\n  "+ dd

#
# Load user configuration
#
config = pd.DataFrame({
	"GLM_NETWORK_PREFIX" : [""],
	"GLM_NETWORK_MATCHES" : [".*"],
	"GLM_NOMINAL_VOLTAGE" : [""],
	"GLM_INCLUDE" : [""],
	"GLM_DEFINE" : [""],
	"GLM_ERRORS" : ["exception"],
	"GLM_WARNINGS" : ["stdout"],
	"GLM_MODIFY" : [""],
	"GLM_ASSUMPTIONS" : ["include"],
	"GLM_NODE_EXTRACT" : ["False"]
	}).transpose().set_axis(["value"],axis=1,inplace=0)
config.index.name = "name" 
if os.path.exists(config_file):
	settings = pd.read_csv(config_file, dtype=str,
		names=["name","value"],
		comment = "#",
		).set_index("name")
elif os.path.exists(f"{os.path.dirname(os.getcwd())}/{config_file}"):
	settings = pd.read_csv(f"{os.path.dirname(os.getcwd())}/{config_file}", dtype=str,
		names=["name","value"],
		comment = "#",
		).set_index("name")
else:
	d = {
		"name" : ["GLM_NOMINAL_VOLTAGE", "GLM_MODIFY", "GLM_WARNINGS"],
		"value" : ["2.40178 kV", "modify.csv", "stdout"]
	}
	settings = pd.DataFrame(data=d).set_index("name")
	print(f"Cannot read {config_file}, use default configurations")
for name, values in settings.iterrows():
	if name in config.index:
		config["value"][name] = values[0]
settings = config["value"]
print(f"Running write_glm.py:")
for name, data in config.iterrows():
	print(f"  {name} = {data['value']}")
default_model_voltage = settings["GLM_NOMINAL_VOLTAGE"][:6]



#
# Phase mapping
#
cyme_phase_name = {0:"ABCN", 1:"A", 2:"B", 3:"C", 4:"AB", 5:"AC", 6:"BC", 7:"ABC"} # CYME phase number -> phase names
glm_phase_code = {"A":1, "B":2, "C":4, "AB":3, "AC":5, "BC":6, "ABC":7} # GLM phase name -> phase number
glm_phase_name = {0:"ABCN", 1:"A",2:"B",3:"AB",4:"C",5:"AC",6:"BC",7:"ABC"} # GLM phase number -> phase name
cyme_phase_name_delta = {1:"AB", 2:"BC", 3:"AC", 7:"ABC"} # CYME phase number -> phase names for delta connection
#
# Device type mapping
#
cyme_devices = {
	1 : "UndergroundLine",
	2 : "OverheadLine",
	3 : "OverheadByPhase",
	4 : "Regulator",
	5 : "Transformer",
	6 : "Not used",
	7 : "Not used",
	8 : "Breaker",
	9 : "LVCB",
	10 : "Recloser",
	11 : "Not used",
	12 : "Sectionalizer",
	13 : "Switch",
	14 : "Fuse",
	15 : "SeriesCapacitor",
	16 : "SeriesReactor",
	17 : "ShuntCapacitor",
	18 : "ShuntReactor",
	19 : "Not used",
	20 : "SpotLoad",
	21 : "DistributedLoad",
	22 : "Miscellaneous",
	23 : "OverheadLineUnbalanced",
	24 : "ArcFurnace",
	25 : "CTypeFilter",
	26 : "DoubleTunedFilter",
	27 : "HighPassFilter",
	28 : "IdealConverter",
	29 : "NonIdealConverter",
	30 : "ShuntFrequencySource",
	31 : "Not used",
	32 : "SingleTunedFilter",
	33 : "InductionMotor",
	34 : "SynchronousMotor",
	35 : "InductionGenerator",
	36 : "SynchronousGenerator",
	37 : "ElectronicConverterGenerator",
	38 : "TransformerByPhase",
	39 : "ThreeWindingTransformer",
	40 : "NetworkEquivalent",
	41 : "Wecs",
	42 : "GroundingTransformer",
	43 : "MicroTurbine",
	44 : "Sofc",
	45 : "Photovoltaic",
	46 : "SeriesFrequencySource",
	47 : "AutoTransformer",
	48 : "ThreeWindingAutoTransformer",
}
glm_devices = {
	1 : "underground_line",
	2 : "overhead_line",
	3 : "overhead_line",
	4 : "regulator",
	5 : "transformer",
	8 : "breaker",
	10 : "recloser",
	# 12 : "sectionalizer",
	13 : "switch",
	14 : "fuse",
	17 : "capacitor",
	20 : "load",
	21 : "load",
	23 : "overhead_line",
	38 : "single_transformer",
}

#
# CYME database access tools
#

# find records in a table (exact field match only)
def table_find(table,**kwargs):
	result = table
	for key,value in kwargs.items():
		result = result[result[key]==value]
	return result

# get the value in a table using a certain id or index
def table_get(table,id,column=None,id_column=None):
	if id_column == None or id_column == '*':
		if column == None or column == "*":
			return table.loc[index]
		else:
			return table.loc[index][column]
	else:
		for index, row in table.iterrows():
			if row[id_column] == id:
				if column == None or column == "*":
					return table.loc[index]
				else:
					return table.loc[index][column]
	return None

def load_cals(load_type,load_phase,connection,load_power1,load_power2,value_type=None):
	phase_number=int(load_phase)
	# default_model_voltage in kV
	if connection == 2: # delta connection
		vol_real = float(default_model_voltage)*cos((1-phase_number)*pi*2.0/3.0+pi/6.0)*1000.0
		vol_imag = float(default_model_voltage)*sin((1-phase_number)*pi*2.0/3.0+pi/6.0)*1000.0
		line_phase_gain = sqrt(3.0) 
		if len(cyme_phase_name_delta[phase_number].replace('N','')) == 2:
			load_scale = 1
		elif len(cyme_phase_name_delta[phase_number].replace('N','')) == 3:
			load_scale = 3
		else:
			raise Exception(f'wrong load phase {load_phase} for delta connection')
	else:
		# wye connecttion
		vol_real = float(default_model_voltage)*cos((1-phase_number)*pi*2.0/3.0)*1000.0
		vol_imag = float(default_model_voltage)*sin((1-phase_number)*pi*2.0/3.0)*1000.0
		line_phase_gain = 1
		load_scale = len(cyme_phase_name[phase_number].replace('N',''))
		if load_scale < 0 or load_scale > 3:
			raise Exception(f'wrong load phase {load_phase} for wye connection')
	if value_type == 0:
		load_real = load_power1 * 1000.0
		load_imag = load_power2 * 1000.0
	elif value_type == 1:
		if load_power2 > 0:
			load_real = load_power1 * load_power2/100 * 1000.0
			load_imag = load_power1 * sqrt(1 - (load_power2/100)**2) * 1000.0
		else:
			load_real = -load_power1 * load_power2/100 * 1000.0
			load_imag = -load_power1 * sqrt(1 - (load_power2/100)**2) * 1000.0
	else:
			load_real = load_power1 * 1000
			if load_power2 > 0.0 or load_power2 < 0.0:
			    load_imag = load_real/(load_power2/100.0)*sqrt(1-abs(load_power2/100)**2)
	vol_mag = float(default_model_voltage)*1000.0
	vol_complex = vol_real+vol_imag*(1j)
	if load_type == "Z":
		if (load_real*load_real + load_imag*load_imag) > 0:
			load_cals_results = vol_mag*line_phase_gain*vol_mag*line_phase_gain/(load_real+load_imag*(1j))/load_scale
			return load_cals_results
		else:
			return 0+0*(1j)
	elif load_type == "I":
		load_cals_results  = (load_real+load_imag*(1j))/(vol_complex*line_phase_gain)/load_scale
		return load_cals_results	
	else:
		# for constant power load, the imag part is negative
		load_cals_results = (load_real-load_imag*(1j))/load_scale
		return load_cals_results

def capacitor_phase_cals(KVARA,KVARB,KVARC):
	return int(KVARA > 0) + 2*int(KVARB > 0) + 3*int(KVARC > 0) + int((KVARA*KVARB > 0) or (KVARA*KVARC > 0) or (KVARB*KVARC > 0))

# Function that replaces characters not allowed in name with '_'
def fix_name(name):
	name = name.replace(' ', '_')
	name = name.replace('.','_')
	name = name.replace('\\','_')
	name = name.replace('/','_')
	name = name.replace(':','_')
	name = name.replace('\'','')
	return name

def arrangeString(string):
	MAX_CHAR = 26
	char_count = [0] * MAX_CHAR
	s = 0

	for i in range(len(string)):
		if string[i] >= "A" and string[i] <= "Z":
			char_count[ord(string[i]) - ord("A")] += 1
		else:
			s += ord(string[i]) - ord("0")
	res = ""

	for i in range(MAX_CHAR):
		ch = chr(ord("A") + i)
		while char_count[i]:
			res += ch
			char_count[i] -= 1
	if s > 0:
		res += str(s)

	return res

def clean_phases(phases):
	p = ''
	if 'A' in phases:
		p = p + 'A'
	if 'B' in phases:
		p = p + 'B'
	if 'C' in phases:
		p = p + 'C'
	return p

#
# Load all the model tables (table names have an "s" appended)
#
cyme_table = {}
cyme_equipment_table = {}
for filename in glob.iglob(f"{data_folder}/*.csv"):
	data = pd.read_csv(filename, dtype=str)
	# index = data.columns[0]
	name = os.path.basename(filename)[0:-4].lower()
	# cyme_table[name] = data.set_index(index)
	cyme_table[name] = data
for filename in cyme_tables_required:
	if filename[3:].lower() not in cyme_table.keys():
#		raise Exception(f"required CYME table '{filename}' is not found in {input_folder}")
		print("Table needed but missing:", filename[3:].lower())
if equipment_file != None:
	if not os.path.exists(f'{data_folder}/cyme_equipment_tables'):
		os.system(f"mkdir -p {data_folder}/cyme_equipment_tables")
	for table in cyme_tables_required:
		csvname = table[3:].lower()
		os.system(f"mdb-export {input_folder}/{equipment_file} {table} > {data_folder}/cyme_equipment_tables/{csvname}.csv")
		row_count = os.popen(f"wc -l {data_folder}/cyme_equipment_tables/{csvname}.csv").read()
		if int(row_count.strip().split(" ")[0]) == 1:
			os.remove(f"{data_folder}/cyme_equipment_tables/{csvname}.csv")

	for filename in glob.iglob(f"{data_folder}/cyme_equipment_tables/*.csv"):
		data = pd.read_csv(filename, dtype=str)
		name = os.path.basename(filename)[0:-4].lower()
		cyme_equipment_table[name] = data
	print(f'Equipment tables: {cyme_equipment_table.keys()}')

#
# store geodata for all node
#
node_geodata = {}

#
# GLM file builder
#
class GLM:

	prefix = {
		# known powerflow class in gridlabd
		"billdump" : "BD_",
		"capacitor" : "CA_",
		"currdump" : "CD_",
		"emissions" : "EM_",
		"fault_check" : "FC_",
		"frequency_gen" : "FG_",
		"fuse" : "FS_",
		"impedance_dump" : "ID_",
		"line" : "LN_",
		"line_configuration" : "LC_",
		"line_sensor" : "LS_",
		"line_spacing" : "LG_",
		"link" : "LK_",
		"load" : "LD_",
		"load_tracker" : "LT_",
		"meter" : "ME_",
		"motor" : "MO_",
		"node" : "ND_",
		"overhead_line" : "OL_",
		"overhead_line_conductor" : "OC_",
		"pole" : "PO_",
		"pole_configuration" : "PC_",
		"power_metrics" : "PM_",
		"powerflow_library" : "PL_",
		"powerflow_object" : "PO_",
		"pqload" : "PQ_",
		"recloser" : "RE_",
		"regulator" : "RG_",
		"regulator_configuration" : "RC_",
		"restoration" : "RS_",
		"sectionalizer" : "SE_",
		"series_reactor" : "SR_",
		"substation" : "SS_",
		"switch" : "SW_",
		"switch_coordinator" : "SC_",
		"transformer" : "TF_",
		"transformer_configuration" : "TC_",
		"triplex_line" : "XL_",
		"triplex_line_conductor" : "XC_",
		"triplex_line_configuration" : "XG_",
		"triplex_load" : "XD_",
		"triplex_meter" : "XM_",
		"triplex_node" : "XN_",
		"underground_line" : "UL_",
		"underground_line_conductor" : "UC_",
		"vfd" : "VF_",
		"volt_var_control" : "VV_",
		"voltdump" : "VD_",
	}

	def __init__(self,file,mode="w"):

		self.filename = file
		self.fh = open(file,mode)
		self.objects = {}
		self.assumptions = []
		self.refcount = {}

	def __del__(self):
		if self.objects:
			self.error("glm object was deleted before objects were output")

	def name(self,name,oclass=None):
		if type(name) is list: # composite name
			name = "_".join(name).replace(".","").replace(":","")[0:63] # disallow special name characters
		if oclass: # name prefix based on class
			if not oclass in self.prefix.keys(): # name prefix not found
				prefix = f"Z{len(self.prefix.keys())}_"
				self.prefix[oclass] = prefix
				warning(f"{cyme_mdbname}@{network_id}: class '{oclass}' is not a known gridlabd powerflow class, using prefix '{prefix}' for names")
			else:
				prefix = self.prefix[oclass]
			name = prefix + name
		elif "0" <= name[0] <= "9": # fix names that start with digits
			name = "_" + name
		return name.replace(" ","_").replace("-","_") # remove white spaces from names

	def write(self,line):
		print(line,file=self.fh)

	def blank(self):
		self.write("")

	def print(self,message):
		self.write(f"#print {message}")

	def warning(self,message):
		self.write(f"#warning {message}")

	def error(self,message):
		self.write(f"#error {message}")

	def comment(self,*lines):
		for line in lines:
			self.write(f"// {line}")

	def set(self,name,value):
		self.write(f"#set {name}={value}")

	def define(self,name,value):
		self.write(f"#define {name}={value}")

	def include(self,name,brackets="\"\""):
		self.write(f"#include {brackets[0]}{name}{brackets[1]}")

	def module(self, name, parameters = {}):
		if not parameters:
			self.write(f"module {name};")
		else:
			self.write(f"module {name}")
			self.write("{")
			for tag, value in parameters.items():
					if type(value) is str:
						self.write(f"\t{tag} \"{value}\";")
					else:
						self.write(f"\t{tag} {value};")
			self.write("}")

	def clock(self, parameters = {}):
		if not parameters:
			raise Exception(f"clock needs parameters")
		else:
			self.write(f"clock")
			self.write("{")
			for tag, value in parameters.items():
					if tag in ["timezone","starttime","stoptime"]:
						self.write(f"\t{tag} \"{value}\";")
					else:
						raise Exception(f"module clock not support parameter {tag}")
			self.write("}")

	def ifdef(self, name, call):
		glm.write(f"#ifdef {name}")
		call()
		glm.write("#endif")

	def ifndef(self, name, call):
		glm.write(f"#ifndef {name}")
		call()
		glm.write("#endif")

	def ifexist(self, name, call):
		glm.write(f"#ifexist {name}")
		call()
		glm.write("#endif")

	def object(self, oclass, name, parameters,overwrite=True):
		if name not in self.objects.keys():
			obj = {"name" : name}
			self.objects[name] = obj
		else:
			obj = self.objects[name]
		if "class" in obj.keys() and obj["class"] == "link" and oclass in ["underground_line","switch","overhead_line","transformer","single_transformer","regulator"]:
			# if obj is created based on a link object
			if oclass == "single_transformer":
				new_name = self.name(name+f"_{parameters['phases']}", "transformer") # new name
				oclass = "transformer"
			else:
				new_name = self.name(name, oclass) # new name
			new_obj = {"name" : new_name}
			self.objects[new_name] = new_obj
			for key, value in obj.items():
				if key != "name":
					new_obj[key] = value
			for key, value in parameters.items():
				if not overwrite and key in new_obj.keys() and new_obj[key] != value:
					raise Exception(f"object property '{key}={new_obj[key]}' merge conflicts with '{key}={value}'")
				if value == None and key in new_obj.keys():
					del new_obj[key]
				else:
					new_obj[key] = value
			new_obj["class"] = oclass
			if "nominal_voltage" in new_obj.keys() and new_obj["class"] == "underground_line":
				del new_obj["nominal_voltage"]
				if "phases" in new_obj.keys() and "N" not in new_obj["phases"]:
					new_obj["phases"] = new_obj["phases"] + "N"
			if new_name in self.refcount.keys():
				self.refcount[new_name] += 1
			else:
				self.refcount[new_name] = 1
			return new_obj
		else:
			for key, value in parameters.items():
				if not overwrite and key in obj.keys() and obj[key] != value:
					raise Exception(f"object property '{key}={obj[key]}' merge conflicts with '{key}={value}'")
				if value == None and key in obj.keys():
					del obj[key]
				else:
					obj[key] = value
			obj["class"] = oclass
			if name in self.refcount.keys():
				self.refcount[name] += 1
			else:
				self.refcount[name] = 1
			return obj


	def delete(self,name):
		if self.refcount[name] == 1:
			del self.objects[name]
		elif self.refcount[name] > 1:
			self.refcount[name] -= 1


	def modify(self,object,property,value,comment=""):
		if comment:
			comment = " // " + str(comment)
		elif not type(comment) is str:
			comment = ""
		if type(value) is str:
			self.write(f"modify {object}.{property} \"{value}\";{comment}")
		else:
			self.write(f"modify {object}.{property} {value};{comment}")

	def assume(self,objname,propname,value,remark=""):
		self.assumptions.append([objname,propname,value,remark])

	def close(self):
		
		# objects
		if self.objects:
			for name, parameters in self.objects.items():
				self.write(f"object {parameters['class']}")
				self.write("{")
				for tag, value in parameters.items():
					if tag != "class":
						if type(value) is str:
							self.write(f"\t{tag} \"{value}\";")
						else:
							self.write(f"\t{tag} {value};")
				self.write("}")
			self.objects = {}

		# assumptions
		if self.assumptions:
			if settings["GLM_ASSUMPTIONS"] == "save":
				filename = f"{settings['GLM_NETWORK_PREFIX']}{cyme_mdbname}_{network_id}_assumptions.glm"
				with open(f"{output_folder}/{filename}","w") as fh:
					print("// Assumptions for GLM conversion from database {cyme_mdbname} network {network_id}",file=fh)
					for row in self.assumptions:
						print(f"modify {row[0]}.{row[1]} \"{row[2]}\"; // {row[3]}",file=fh)
			elif settings["GLM_ASSUMPTIONS"] == "include":
				self.blank()
				self.comment("","Assumptions","")
				for row in self.assumptions:
					self.modify(row[0],row[1],row[2],row[3])
			elif settings["GLM_ASSUMPTIONS"] == "warn":
				filename = f"{output_folder}/{cyme_mdbname}_{network_id}_assumptions.csv"
				warning(f"{cyme_mdbname}@{network_id}: {len(self.assumptions)} assumptions made, see '{filename}' for details")
				pd.DataFrame(self.assumptions).to_csv(filename,header=["object_name","property_name","value","remark"],index=False)
			elif settings["GLM_ASSUMPTIONS"] != "ignore":
				warning(f"GLM_ASSUMPTIONS={settings['GLM_ASSUMPTIONS']} is not valid (must be one of 'save','ignore','warn','include')")
		
		# modifications
		for modify in settings["GLM_MODIFY"].split():
			self.blank()
			self.comment("",f"Modifications from '{modify}'","")
			try:
				with open(f"{input_folder}/{modify}","r") as fh:
					reader = csv.reader(fh)
					for row in reader:
						if len(row) == 0:
							warning(f"No modifications from {modify}")
						elif 0 < len(row) < 3:
							warning(f"{modify}: row '{','.join(list(row))}' is missing one or more required fields")
						elif len(row) > 3:
							warning(f"{modify}: row '{','.join(list(row))}' has extra fields that will be ignored")
							self.modify(*row[0:3])
						else:
							self.modify(*row)
			except:
				pass

	# general glm model add function
	def add(self,oclass,device_id,data,version,**kwargs):
		try:
			call = getattr(self,"add_"+oclass)
			return call(device_id,data,version=version,**kwargs)
		except Exception as errmsg:
			warning(f"{cyme_mdbname}@{network_id}: unable to add gridlabd class '{oclass}' using CYME device '{device_id}': {errmsg} {format_exception(errmsg,device_id,data.to_dict())}")
			pass 	

	# add a link to glm file
	def add_link(self,section_id,section,version,**kwargs):
		phase = int(section["Phase"])
		from_node_id = fix_name(section["FromNodeId"])
		to_node_id = fix_name(section["ToNodeId"])
		device_dict = {}
		for index, device in table_find(cyme_table["sectiondevice"],SectionId=section_id).iterrows():
			device_id = fix_name(device["DeviceNumber"])
			device_type = int(device["DeviceType"])
			if device_type in glm_devices.keys():
				device_name = self.name(device_id,"link")
				device_dict[device_id] = self.object("link", device_name , {
					"phases" : cyme_phase_name[phase],
					"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
					"from" : self.name(from_node_id,"node"),
					"to" : self.name(to_node_id,"node"),
					})
				kwargs["node_links"][from_node_id].append(device_id)
				kwargs["node_links"][to_node_id].append(device_id)
			else:
				warning(f"{cyme_mdbname}@{network_id}: {cyme_devices[device_type]} on section {section_id} has no corresponding GLM object")
		# print(device_dict)
		return device_dict

	# add node to glm file
	def add_node(self,node_id,node_links,device_dict,version):
		phase = 0
		# if node_id not in node_geodata.keys():
		# 	node_X = table_get(cyme_table["node"],node_id,"X","NodeId")
		# 	node_Y = table_get(cyme_table["node"],node_id,"Y","NodeId")
		# 	node_geodata[node_id] = {
		# 		"NotworkID" : network_id,
		# 		"X" : node_X,
		# 		"Y" : node_Y,
		# 	}
		# else:
		# 	if node_geodata[node_id]["NetworkId"] != network_id:
		# 		node_geodata[f"{node_id}_{network_id}"] = {
		# 			"NotworkID" : network_id,
		# 			"X" : node_X,
		# 			"Y" : node_Y,
		# 		}
		# 	else:
		# 		raise Exception(f"{cyme_mdbname}@{network_id}: multiple definition for {node_id}")
		for device_id in node_links[node_id]:
			phase |= glm_phase_code[device_dict[device_id]["phases"]]
		obj = self.object("node", self.name(node_id,"node"), {
			"phases" : glm_phase_name[phase]+"N",
			"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
			})
		if node_id == table_get(cyme_table["headnode"],network_id,"NodeId","NetworkId"):
			obj["bustype"] = "SWING"
		else:
			obj["bustype"] = "PQ"
		return obj

	# add an overhead line based on a link
	def add_overhead_line(self,line_id,line,version):
		line_name = self.name(line_id,"link")
		length = float(line["Length"])
		if length == 0.0:
			length = 0.01
		line_conductor_id = line["LineId"]
		line_conductor = None
		if 'eqconductor' in cyme_equipment_table.keys():
			line_conductor = table_get(cyme_equipment_table['eqoverheadline'],line_conductor_id,None,'EquipmentId')
		# elif 'csvundergroundcable' in cyme_equipment_table.keys():
		# 	## TODO
		elif 'eqconductor' in cyme_table.keys():
			line_conductor = table_get(cyme_table['eqoverheadline'],line_conductor_id,None,'EquipmentId')
		if line_conductor is None:
			raise Exception(f'{cyme_mdbname}@{network_id}: cable conductor "{line_conductor_id}" of line "{line_id}" is missing in CYME model.')
		conductorABC_id = line_conductor["PhaseConductorId"]
		conductorN_id = line_conductor["NeutralConductorId"]
		self.add_overhead_line_conductors([conductorABC_id,conductorN_id],version)
		spacing_id = line_conductor["ConductorSpacingId"]
		self.add_line_spacing(spacing_id,version)
		configuration_name = self.add_line_configuration([conductorABC_id,conductorABC_id,conductorABC_id,conductorN_id,spacing_id],version)
		return self.object("overhead_line", line_name, {
			"length" : "%.2f m"%length,
			"configuration" : configuration_name,
			})

	# add an overhead line by phase based on a link
	def add_overhead_line_phase(self,line_id,line,version):
		line_name = self.name(line_id,"link")
		length = float(line["Length"])
		if length == 0.0:
			length = 0.01
		conductorA_id = line["PhaseConductorIdA"]
		conductorB_id = line["PhaseConductorIdB"]
		conductorC_id = line["PhaseConductorIdC"]
		conductorN_id = line["NeutralConductorId"]
		self.add_overhead_line_conductors([conductorA_id,conductorB_id,conductorC_id,conductorN_id],version)
		spacing_id = line["ConductorSpacingId"]
		self.add_line_spacing(spacing_id,version)
		configuration_name = self.add_line_configuration([conductorA_id,conductorB_id,conductorC_id,conductorN_id,spacing_id],version)
		return self.object("overhead_line", line_name, {
			"length" : "%.2f m"%length,
			"configuration" : configuration_name,
			})

	# add an unbalanced overhead line based on a link
	def add_overhead_line_unbalanced(self,line_id,line,version):
		line_name = self.name(line_id,"link")
		configuration_id = line["LineId"]
		configuration_name = self.name(configuration_id,"line_configuration")
		length = float(line["Length"])
		if length == 0.0:
			length = 0.01
		if not configuration_name in self.objects.keys():
			configuration = table_get(cyme_table['eqoverheadlineunbalanced'],configuration_id,None,'EquipmentId')
			conductorA_id = configuration["PhaseConductorIdA"]
			conductorB_id = configuration["PhaseConductorIdB"]
			conductorC_id = configuration["PhaseConductorIdC"]
			conductorN_id = configuration["NeutralConductorId"]
			conductor_names = self.add_overhead_line_conductors([conductorA_id,conductorB_id,conductorC_id,conductorN_id],version)
			spacing_id = configuration["ConductorSpacingId"]
			spacing_name = self.add_line_spacing(spacing_id,version)
			self.object("line_configuration",configuration_name,{
				"conductor_A" : conductor_names[0],
				"conductor_B" : conductor_names[1],
				"conductor_C" : conductor_names[2],
				"conductor_N" : conductor_names[3],
				"spacing" : spacing_name,
				})
		return self.object("overhead_line", line_name, {
			"length" : "%.2f m"%length,
			"configuration" : configuration_name,
			})

	# add an underground line based on a link
	def add_underground_line(self,line_id,line,version):
		line_name = self.name(line_id,"link")
		if version == 5020:
			## SCE feeder UG line length unit is km
			## TODO
			length = float(line["Length"])*1000
		else:
			length = float(line["Length"])
		if length == 0.0:
			length = 0.01
		cable_conductor_id = line["CableId"]
		cable_conductor_flag = None
		conductor_name = self.name(cable_conductor_id,"underground_line_conductor")
		if 'eqconductor' in cyme_equipment_table.keys():
			cable_conductor = table_get(cyme_equipment_table['eqconductor'],cable_conductor_id,None,'EquipmentId')
		# elif 'csvundergroundcable' in cyme_equipment_table.keys():
		# 	## TODO
		elif 'eqconductor' in cyme_table.keys():
			cable_conductor = table_get(cyme_table['eqconductor'],cable_conductor_id,None,'EquipmentId')
		if not conductor_name in self.objects.keys():
			if cable_conductor is None:
				warning(f"{cyme_mdbname}@{network_id}: cable conductor {cable_conductor_id} of line '{line_id}' is missing in CYME model, use default settings instead.")
				# only use default settings for now
				self.object("underground_line_conductor",conductor_name,{
					"outer_diameter" : "0.968 cm",
					"conductor_gmr" : "0.0319 cm",
					"conductor_diameter" : "0.968 cm",
					"conductor_resistance" : "0.139 Ohm/km",
					"neutral_gmr" : "0.00208 cm",
					"neutral_resistance" : "14.8722 Ohm/km",
					"neutral_diameter" : "0.0641 cm",
					"neutral_strands" : "16",
					"shield_gmr" : "0.0 cm",
					"shield_resistance" : "0.0 Ohm/km",
					"rating.summer.continuous" : "500 A",
					})
			else:
				gmr = float(cable_conductor["GMR"])
				r25 = float(cable_conductor["R25"])
				diameter = float(cable_conductor["Diameter"])
				nominal_rating = float(cable_conductor["FirstRating"])
				if nominal_rating == 0:
					nominal_rating = 1000				
				if r25 == 0:
					r25 = 0.00001
				obj = self.object("underground_line_conductor",conductor_name,{
					"outer_diameter" : "%.2f cm" % diameter,
					"conductor_gmr" : "%.2f cm" % gmr,
					"conductor_diameter" : "%.2f cm" % diameter,
					"conductor_resistance" : "%.5f Ohm/km" % r25,
					"neutral_gmr" : "0.00208 cm",
					"neutral_resistance" : "14.8722 Ohm/km",
					"neutral_diameter" : "0.0641 cm",
					"neutral_strands" : "16",
					"shield_gmr" : "0.0 cm",
					"shield_resistance" : "0.0 Ohm/km",
					"rating.summer.continuous" : "%.1f A" % nominal_rating,
					})
		try:
			line_phases = self.objects[line_name]['phases']
		except:
			raise Exception(f'cannot find the link objects for underground line {line_id}')
		if "N" not in line_phases:
			line_phases = line_phases + "N"
		spacing_name = self.name(f'UL_{line_id}_{line_phases}',"line_spacing")
		if not spacing_name in self.objects.keys():
			# only use default settings for now
			UL_spacings = {}
			if 'A' in line_phases and 'B' in line_phases:
				UL_spacings['distance_AB'] = str(0.1)
			if 'B' in line_phases and 'C' in line_phases:
				UL_spacings['distance_BC'] = str(0.1)
			if 'A' in line_phases and 'C' in line_phases:
				UL_spacings['distance_AC'] = str(0.1)
			if 'A' in line_phases:
				UL_spacings['distance_AN'] = str(0.0477)
			if 'B' in line_phases:
				UL_spacings['distance_BN'] = str(0.0477)
			if 'C' in line_phases:
				UL_spacings['distance_CN'] = str(0.0477)
			self.object("line_spacing",spacing_name,UL_spacings)
		configuration_name = self.name(f'UL_{line_id}_{line_phases}',"line_configuration")
		if not configuration_name in self.objects.keys():
			UL_configs = {}
			if 'A' in line_phases:
				UL_configs['conductor_A'] = conductor_name
			if 'B' in line_phases:
				UL_configs['conductor_B'] = conductor_name
			if 'C' in line_phases:
				UL_configs['conductor_C'] = conductor_name
			if 'N' in line_phases:
				UL_configs['conductor_N'] = conductor_name
			UL_configs['spacing'] = spacing_name
			self.object("line_configuration",configuration_name,UL_configs)
		return self.object("underground_line", line_name, {
			"length" : "%.2f m"%length,
			"configuration" : configuration_name,
			})

	# add overhead line conductor library entry
	def add_overhead_line_conductors(self,conductors,version):
		conductor_names = []
		for conductor_id in conductors:
			conductor_name = self.name(conductor_id,"overhead_line_conductor")
			conductor = None
			if not conductor_name in self.objects.keys():
				if 'eqconductor' in cyme_equipment_table.keys():
					conductor = table_get(cyme_equipment_table['eqconductor'],conductor_id,None,'EquipmentId')
				elif 'eqconductor' in cyme_table.keys():
					conductor = table_get(cyme_table['eqconductor'],conductor_id,None,'EquipmentId')
				else:
					# use default settings. TODO
					raise Exception(f"cannot add cable conductor {conductor_name} for version {version}")
				if conductor is None:
					raise Exception(f"cannot add cable conductor {conductor_name} for version {version}")
				else:
					gmr = float(conductor["GMR"])
					r25 = float(conductor["R25"])
					diameter = float(conductor["Diameter"])
					nominal_rating = float(conductor["NominalRating"])
					# should set up NONE conductor rating and resistance as non-zero value
					# cannot use modify.csv to change the ratings fior OC_NONE
					if nominal_rating == 0:
						nominal_rating = 1000				
					if r25 == 0:
						r25 = 0.00001
					obj = self.object("overhead_line_conductor",conductor_name,{
						"geometric_mean_radius" : "%.2f cm" % gmr,
						"resistance" : "%.5f Ohm/km" % r25,
						"diameter" : "%.2f cm" % diameter,
						"rating.summer.continuous" : "%.1f A" % nominal_rating,
						"rating.winter.continuous" : "%.1f A" % nominal_rating,
						"rating.summer.emergency" : "%.1f A" % nominal_rating,
						"rating.winter.emergency" : "%.1f A" % nominal_rating,
						})
			conductor_names.append(conductor_name)
		return conductor_names

	# line spacing library object
	def add_line_spacing(self,spacing_id,version):
		spacing_name = self.name(spacing_id,"line_spacing")
		if not spacing_name in self.objects.keys():
			spacing = None
			if 'eqgeometricalarrangement' in cyme_equipment_table.keys():
				spacing = table_get(cyme_equipment_table['eqgeometricalarrangement'],spacing_id,None,'EquipmentId')
			elif 'eqgeometricalarrangement' in cyme_table.keys():
				spacing = table_get(cyme_table['eqgeometricalarrangement'],spacing_id,None,'EquipmentId')
			else:
				# use default settings. TODO
				raise Exception(f"cannot add cable spacing {spacing_id} for version {version}")
			if spacing is None:
				raise Exception(f"cannot add cable spacing {spacing_id} for version {version}")
			else:
				Ax = float(spacing["ConductorA_Horizontal"])
				Ay = float(spacing["ConductorA_Vertical"])
				Bx = float(spacing["ConductorB_Horizontal"])
				By = float(spacing["ConductorB_Vertical"])
				Cx = float(spacing["ConductorC_Horizontal"])
				Cy = float(spacing["ConductorC_Vertical"])
				Nx = float(spacing["NeutralConductor_Horizontal"])
				Ny = float(spacing["NeutralConductor_Vertical"])
				ABx = Ax-Bx; ABy = Ay-By
				ACx = Ax-Cx; ACy = Ay-Cy
				BCx = Bx-Cx; BCy = By-Cy
				ANx = Ax-Nx; ANy = Ay-Ny
				BNx = Bx-Nx; BNy = By-Ny
				CNx = Cx-Nx; CNy = Cy-Ny
				self.object("line_spacing",spacing_name,{
					"distance_AB" : "%.2f m"%sqrt(ABx*ABx+ABy*ABy),
					"distance_AC" : "%.2f m"%sqrt(ACx*ACx+ACy*ACy),
					"distance_BC" : "%.2f m"%sqrt(BCx*BCx+BCy*BCy),
					"distance_AN" : "%.2f m"%sqrt(ANx*ANx+ANy*ANy),
					"distance_BN" : "%.2f m"%sqrt(BNx*BNx+BNy*BNy),
					"distance_CN" : "%.2f m"%sqrt(CNx*CNx+CNy*CNy),
					"distance_AE" : "%.2f m"%Ay,
					"distance_BE" : "%.2f m"%By,
					"distance_CE" : "%.2f m"%Cy,
					"distance_NE" : "%.2f m"%Ny,
					})
		return spacing_name

	# line configuration library object
	def add_line_configuration(self,items,version):
		configuration_id = "_".join(items)
		configuration_name = self.name(configuration_id,"line_configuration")
		if not configuration_name in self.objects.keys():
			self.object("line_configuration",configuration_name,{
				"conductor_A" : self.name(items[0],"overhead_line_conductor"),
				"conductor_B" : self.name(items[1],"overhead_line_conductor"),
				"conductor_C" : self.name(items[2],"overhead_line_conductor"),
				"conductor_N" : self.name(items[3],"overhead_line_conductor"),
				"spacing" : self.name(items[4],"line_spacing")
				})
		return configuration_name

	# add a switch based on a link
	def add_switch(self,switch_id,switch,version):
		switch_name = self.name(switch_id,"link")
		phases = cyme_phase_name[int(switch["ClosedPhase"])]
		switch_config = {
		"operating_mode" : "BANKED"
		}
		for phase in phases:
			if phase != "N":
				switch_config[f'phase_{phase}_state'] = "CLOSED"
		return self.object("switch", switch_name, switch_config,overwrite=False)

	# add a breaker based on a link
	def add_breaker(self,breaker_id,breaker,version):
		breaker_name = self.name(breaker_id,"link")
		phases = cyme_phase_name[int(breaker["ClosedPhase"])]
		breaker_config = {
		"operating_mode" : "BANKED"
		}
		for phase in phases:
			if phase != "N":
				breaker_config[f'phase_{phase}_state'] = "CLOSED"
		return self.object("switch", breaker_name, breaker_config,overwrite=False)

	# add a recloser based on a link
	def add_recloser(self,recloser_id,recloser,version):
		recloser_name = self.name(recloser_id,"link")
		phases = cyme_phase_name[int(recloser["ClosedPhase"])]
		recloser_config = {
		"operating_mode" : "BANKED"
		}
		for phase in phases:
			if phase != "N":
				recloser_config[f'phase_{phase}_state'] = "CLOSED"
		return self.object("switch", recloser_name, recloser_config,overwrite=False)

	# add a fuse based on a link
	def add_fuse(self,fuse_id,fuse,version):
		fuse_name = self.name(fuse_id,"link")
		phases = cyme_phase_name[int(fuse["ClosedPhase"])]
		fuse_config = {
		"operating_mode" : "BANKED"
		}
		for phase in phases:
			if phase != "N":
				fuse_config[f'phase_{phase}_state'] = "CLOSED"
		return self.object("switch", fuse_name, fuse_config,overwrite=False)

	# add a load
	def add_load(self,load_id,load,version,**kwargs):
		section_id = table_get(cyme_table["sectiondevice"],load_id,"SectionId","DeviceNumber")
		section = table_get(cyme_table["section"],section_id,None,"SectionId")
		device_type = int(load["DeviceType"])
		value_type = int(load["LoadValueType"])
		connection_type = int(table_get(cyme_table["load"],load_id,"ConnectionConfiguration","DeviceNumber"))
		if device_type == 20: # spot load is attached at from node of section
			parent_name = self.name(section["FromNodeId"],"node")
		elif device_type == 21: # distributed load is attached at to node of section
			parent_name = self.name(section["ToNodeId"],"node")
		else:
			raise Exception(f"CYME device type {device_type} is not supported as a load")

		if parent_name not in self.objects.keys():
			# Definition for node "parent_name" is missing
			device_dict = kwargs["node_info"]["Device_Dicts"]
			node_links = kwargs["node_info"]["Node_Links"]
			self.add_node(parent_name[3:],node_links,device_dict,version)

		customer_id = load["CustomerNumber"]

		link_name = self.name(load_id,"link")
		if link_name in self.objects.keys(): # link is no longer needed
			self.delete(link_name)
		load_name = self.name(load_id,"load")
		device_type = int(load["DeviceType"])
		phase = cyme_phase_name[int(load["Phase"])]
		if load_name in self.objects.keys() and "phases" in self.objects[load_name]:
			phases = self.objects[load_name]["phases"] + phase
		else:
			phases = phase
		if device_type in glm_devices.keys():
			ConsumerClassId = load["ConsumerClassId"]
			# the default load unit in gridlabd is Volt-Amperes, or Amperes or Ohms
			load_value1 = float(load["LoadValue1"])
			load_value2 = float(load["LoadValue2"])
			# from the mdb file, type for constant power load is defined as PQ
			load_types = {"Z":"constant_impedance","I":"constant_current","PQ":"constant_power"}
			if ConsumerClassId in load_types.keys():
				load_cals_complex = load_cals(ConsumerClassId,load["Phase"],connection_type,load_value1,load_value2,value_type)
				load_value1 = load_cals_complex.real
				load_value2 = -load_cals_complex.imag
				if (load_value1*load_value1 + load_value2*load_value2) > 0:
					load_dict = {
						"parent" : parent_name,
						"phases" : arrangeString(phases),
						"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
					}
					for i_phase in phase:
						load_dict[f"{load_types[ConsumerClassId]}_{i_phase}"] = "%.4g%+.4gj" % (load_value1,load_value2)
					return self.object("load",load_name,load_dict)
			elif ConsumerClassId in ["PV","SWING","SWINGPQ"]: 
				# GLM bus types allowed
				load_cals_complex = load_cals("Z",load["Phase"],connection_type,load_value1,load_value2,value_type)
				load_value1 = load_cals_complex.real
				load_value2 = -load_cals_complex.imag
				if (load_value1*load_value1 + load_value2*load_value2) > 0:
					load_dict = {
						"parent" : parent_name,
						"phases" : arrangeString(phases),
						"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
						"bustype" : ConsumerClassId,
					}
					for i_phase in phase:
						load_dict[f"constant_impedance_{i_phase}"] = "%.4g%+.4gj" % (load_value1,load_value2)
					return self.object("load",load_name,load_dict)
			elif ConsumerClassId in ["CGSUB","Other","Industrial","Residential"]:
				# GLM bus types allowed
				load_cals_complex = load_cals("PQ",load["Phase"],connection_type,load_value1,load_value2,value_type)
				load_value1 = load_cals_complex.real
				load_value2 = -load_cals_complex.imag
				if (load_value1*load_value1 + load_value2*load_value2) > 0:
					load_dict = {
						"parent" : parent_name,
						"phases" : arrangeString(phases),
						"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
					}
					for i_phase in phase:
						load_dict[f"constant_power_{i_phase}"] = "%.4g%+.4gj" % (load_value1,load_value2)
					return self.object("load",load_name,load_dict)
			else:
				warning(f"{cyme_mdbname}@{network_id}: load '{load_id}' on phase '{phase}' dropped because '{ConsumerClassId}' is not a supported CYME load type")
		else:
			warning(f"{cyme_mdbname}@{network_id}: load '{load_id}' on phase '{phase}' dropped because '{cyme_devices[device_type]}' is not a supported CYME device type")

	# add a capacitor
	def add_capacitor(self,capacitor_id,capacitor,version,**kwargs):
		section_id = table_get(cyme_table["sectiondevice"],capacitor_id,"SectionId","DeviceNumber")
		section = table_get(cyme_table["section"],section_id,None,"SectionId")
		from_name = self.name(section["FromNodeId"],"node")
		to_name = self.name(section["ToNodeId"],"node")
		equipment_id = capacitor["EquipmentId"]
		if 'eqtransformer' in cyme_equipment_table.keys():
			equipment = table_get(cyme_equipment_table["eqshuntcapacitor"],equipment_id,None,"EquipmentId")
		# if from_name not in self.objects.keys():
		# 	# Definition for node "from_name" is missing
		# 	device_dict = kwargs["node_info"]["Device_Dicts"]
		# 	node_links = kwargs["node_info"]["Node_Links"]
		# 	self.add_node(from_name[3:],node_links,device_dict,version)

		link_name = self.name(capacitor_id,"link")
		if link_name in self.objects.keys(): # link is no longer needed
			self.delete(link_name)
		KVARA = float(capacitor["KVARA"])
		if "SwitchedKVARA" in capacitor.keys(): # for NG MDB files
			KVARA = KVARA + float(capacitor["SwitchedKVARA"])
		KVARB = float(capacitor["KVARB"])
		if "SwitchedKVARB" in capacitor.keys(): # for NG MDB files
			KVARB = KVARB + float(capacitor["SwitchedKVARB"])
		KVARC = float(capacitor["KVARC"])
		if "SwitchedKVARC" in capacitor.keys(): # for NG MDB files
			KVARC = KVARC + float(capacitor["SwitchedKVARC"])
		if not KVARA + KVARB + KVARC > 0.0:
			warning(f"{cyme_mdbname}@{network_id}: capacitor {capacitor_id} has zero capacitance for all phases.")
			return
		KVLN = float(capacitor["KVLN"])
		ConnectionConfig = int(capacitor["ConnectionConfiguration"]) # 2 for delta and else for wye
		capacitor_name = self.name(capacitor_id,"capacitor")
		control = "MANUAL"
		self.assume(capacitor_name,"control",control,f"capacitor {capacitor_id} does not specify a control strategy, valid options are 'CURRENT', 'VARVOLT', 'VOLT', 'VAR', or 'MANUAL'")

		if "Phase" in capacitor.keys():
			phase = cyme_phase_name[int(capacitor["Phase"])]
		elif "ByPhase" in capacitor.keys():
			phase = cyme_phase_name[int(capacitor["ByPhase"])]
		else:
			warning(f"{cyme_mdbname}@{network_id}: capacitor {capacitor_id} does not specify {err}, phase will be specified based on capacitance data")
			phase = cyme_phase_name[capacitor_phase_cals(KVARA,KVARB,KVARC)]

		capacitor_dict = {
				"parent" : from_name,
				"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
				"control" : "MANUAL",
		}
		phase = ""
		if KVARA > 0.0:
			capacitor_dict["capacitor_A"] = f"{KVARA} kVA"
			capacitor_dict["switchA"]  = "CLOSED"
			if ConnectionConfig == 2:
				phase = phase + "AB"
			else:
				phase = phase + "A"
		else:
			capacitor_dict["capacitor_A"] = f"0 kVA"
			capacitor_dict["switchA"]  = "OPEN"
		if KVARB > 0.0:
			capacitor_dict["capacitor_B"] = f"{KVARB} kVA"
			if ConnectionConfig == 2:
				phase = phase + "BC"
			else:
				phase = phase + "B"
		else:
			capacitor_dict["capacitor_B"] = f"0 kVA"
			capacitor_dict["switchB"]  = "OPEN"
		if KVARC > 0.0:
			capacitor_dict["capacitor_C"] = f"{KVARC} kVA"
			if ConnectionConfig == 2:
				phase = phase + "AC"
			else:
				phase = phase + "C"
		else:
			capacitor_dict["capacitor_C"] = f"0 kVA"
			capacitor_dict["switchC"]  = "OPEN"
		phase = clean_phases(phase)
		if ConnectionConfig == 0 and "N" not in phase:
			phase = phase + "N"
		elif ConnectionConfig > 0 and "N" in phase:
			phase.replace("N","")
		capacitor_dict["phases"] = phase
		capacitor_dict["phases_connected"] = phase
		return self.object("capacitor",capacitor_name,capacitor_dict)

	# add a transformer
	def add_transformer(self,transformer_id, transformer,version):
		DeviceType = int(transformer["DeviceType"])
		equipment_id = transformer["EquipmentId"]
		if 'eqtransformer' in cyme_equipment_table.keys():
			equipment = table_get(cyme_equipment_table["eqtransformer"],equipment_id,None,"EquipmentId")
		elif 'eqtransformer' in cyme_table.keys():
			equipment = table_get(cyme_table["eqtransformer"],equipment_id,None,"EquipmentId")
		else:
			raise Exception(f"cannot find cyme table 'eqtransformer'.")
		NominalRatingKVA = float(equipment["NominalRatingKVA"])
		PrimaryVoltageKVLL = float(equipment["PrimaryVoltageKVLL"])
		SecondaryVoltageKVLL = float(equipment["SecondaryVoltageKVLL"])
		PosSeqImpedancePercent = float(equipment["PosSeqImpedancePercent"])
		XRRatio = float(equipment["XRRatio"])
		r = XRRatio / 100.0 / sqrt(1+XRRatio**2)
		x = r * XRRatio
		nominal_rating = "%.4gkVA" % (NominalRatingKVA)
		primary_voltage = "%.4gkV" % (PrimaryVoltageKVLL/sqrt(3.0))
		secondary_voltage = "%.4gkV" % (SecondaryVoltageKVLL/sqrt(3.0))
		configuration_name = self.name([nominal_rating,primary_voltage,secondary_voltage,"R%.4g"%(r),"X%4g"%(x)], "transformer_configuration")
		if primary_voltage == secondary_voltage:
			secondary_voltage = "%.4gkV" % ((SecondaryVoltageKVLL+0.001)/sqrt(3.0))
			self.assume(configuration_name,"secondary_voltage",secondary_voltage,f"transformer {transformer_id} primary voltage is the same as secondary voltage")
		if r == 0.0:
			r = 0.000333
			x = 0.00222
			self.assume(configuration_name,"resistance",r,f"transformer {transformer_id} XRRatio is zero")
			self.assume(configuration_name,"reactance",x,f"transformer {transformer_id} XRRatio is zero")

		connect_type = "WYE_WYE"
		self.assume(configuration_name,"connect_type",connect_type,f"transformer '{transformer_id}' does not specify connection type")
		install_type = "PADMOUNT"
		self.assume(configuration_name,"install_type",install_type,f"transformer '{transformer_id}' does not specify install type")

		self.object("transformer_configuration", configuration_name, {
			"connect_type" : "WYE_WYE",
			"install_type" : "PADMOUNT",
			"power_rating" : "%.4gkVA" % (NominalRatingKVA),
			"primary_voltage" : primary_voltage,
			"secondary_voltage" : secondary_voltage,
			"resistance" : r,
			"reactance" : x,
			})
		# add a transformer based on a link
		link_name = self.name(transformer_id,"link")
		return self.object("transformer", link_name, {
			"nominal_voltage" : None,
			"phases" : "".join(sorted(set(self.objects[link_name]["phases"] + "N"))),
			"configuration" : configuration_name,
			})

	# add a single phase transformer
	def add_single_transformer(self,transformer_id, transformer,version):
		for n in range(1,4):
			equipment_id = transformer[f"PhaseTransformerID{n}"]
			if isinstance(equipment_id, str):
				equipment = table_get(cyme_equipment_table["eqtransformer"],equipment_id,None,"EquipmentId")
				NominalRatingKVA = float(equipment["NominalRatingKVA"])
				PrimaryVoltageKVLL = float(equipment["PrimaryVoltageKVLL"])
				SecondaryVoltageKVLL = float(equipment["SecondaryVoltageKVLL"])
				PosSeqImpedancePercent = float(equipment["PosSeqImpedancePercent"])
				XRRatio = float(equipment["XRRatio"])
				r = XRRatio / 100.0 / sqrt(1+XRRatio**2)
				x = r * XRRatio
				nominal_rating = "%.4gkVA" % (NominalRatingKVA)
				primary_voltage = "%.4gkV" % (PrimaryVoltageKVLL/sqrt(3.0))
				secondary_voltage = "%.4gkV" % (SecondaryVoltageKVLL/sqrt(3.0))
				configuration_name = self.name([nominal_rating,primary_voltage,secondary_voltage,"R%.4g"%(r),"X%4g"%(x),cyme_phase_name[n]], "transformer_configuration")
				if primary_voltage == secondary_voltage:
					secondary_voltage = "%.4gkV" % ((SecondaryVoltageKVLL+0.001)/sqrt(3.0))
					self.assume(configuration_name,"secondary_voltage",secondary_voltage,f"transformer {transformer_id} primary voltage is the same as secondary voltage")
				if r == 0.0:
					r = 0.000333
					x = 0.00222
					self.assume(configuration_name,"resistance",r,f"transformer {transformer_id} XRRatio is zero")
					self.assume(configuration_name,"reactance",x,f"transformer {transformer_id} XRRatio is zero")
				connect_type = "SINGLE_PHASE"
				self.assume(configuration_name,"connect_type",connect_type,f"transformer '{transformer_id}' does not specify connection type")
				install_type = "PADMOUNT"
				self.assume(configuration_name,"install_type",install_type,f"transformer '{transformer_id}' does not specify install type")

				self.object("transformer_configuration", configuration_name, {
					"connect_type" : connect_type,
					"install_type" : install_type,
					"power_rating" : "%.4gkVA" % (NominalRatingKVA),
					"primary_voltage" : primary_voltage,
					"secondary_voltage" : secondary_voltage,
					"resistance" : r,
					"reactance" : x,
					})
				link_name = self.name(transformer_id,"link")
				self.object("single_transformer", link_name, {
					"nominal_voltage" : None,
					"phases" : "".join(sorted(set(cyme_phase_name[n] + "N"))),
					"configuration" : configuration_name,
					})

	# add a regulator
	def add_regulator(self, regulator_id, regulator, version):
		equipment_id = regulator["EquipmentId"]
		if 'eqregulator' in cyme_equipment_table.keys():
			equipment = table_get(cyme_equipment_table["eqregulator"],equipment_id,None,"EquipmentId")
		elif 'eqregulator' in cyme_table.keys():
			equipment = table_get(cyme_table["eqregulator"],equipment_id,None,"EquipmentId")
		else:
			raise Exception(f"cannot find cyme table 'eqtransformer'.")
		CTPrimaryRating = float(regulator["CTPrimaryRating"])
		PTRatio = float(regulator["PTRatio"])
		try:
			BandWidth = float(regulator["BandWidth"])
		except KeyError as err:
			warning(f"Regulator '{regulator_id}' doesn't define {err}, default value will be used")
			BandWidth = 2.0
		BoostPercent = float(regulator["BoostPercent"])
		BuckPercent = float(regulator["BuckPercent"])
		TapPositionA = float(regulator["TapPositionA"])
		TapPositionB = float(regulator["TapPositionB"])
		TapPositionC = float(regulator["TapPositionC"])
		ControlStatus = float(regulator["ControlStatus"])
		ReverseSensingMode = float(regulator["ReverseSensingMode"])
		ReverseThreshold = float(regulator["ReverseThreshold"])
		X = float(regulator["X"])
		Y = float(regulator["Y"])
		Status = int(regulator["Status"])
		Reversible = int(regulator["Reversible"])

		RatedKVA = float(equipment["RatedKVA"])
		RatedKVLN = float(equipment["RatedKVLN"])
		NumberOfTaps = int(equipment["NumberOfTaps"])

		connect_type = "WYE_WYE"
		Control = "OUTPUT_VOLTAGE"
		time_delay = "30s"
		band_center = "${GLM_NOMINAL_VOLTAGE}"
		band_width = "%.1gV" % (BandWidth)

		configuration_name = self.name([regulator_id,band_width,time_delay],"regulator_configuration")
		self.assume(configuration_name,"connect_type",connect_type,f"regulator '{regulator_id}' does not specify connection type")
		self.assume(configuration_name,"Control",Control,f"regulator '{regulator_id}' does not specify control type")
		self.assume(configuration_name,"time_delay",time_delay,f"regulator '{regulator_id}' does not specify time delay")
		self.assume(configuration_name,"band_center",band_center,f"regulator '{regulator_id}' does not specify band center")

		self.object("regulator_configuration", configuration_name, {
			"connect_type" : connect_type,
			"band_center" : band_center,
			"band_width" : band_width,
			"time_delay" : time_delay,
			"raise_taps" : "%.0f" % float(NumberOfTaps/2),
			"lower_taps" : "%.0f" % float(NumberOfTaps/2),
			"current_transducer_ratio" : "%.0f" % CTPrimaryRating,
			"power_transducer_ratio" : "%.0f" % PTRatio,
			"regulation" : "%.4f%%" % (BandWidth / (RatedKVLN*1000) * 100),
			"tap_pos_A" : "%.0f" % (TapPositionA),
			"tap_pos_B" : "%.0f" % (TapPositionB),
			"tap_pos_C" : "%.0f" % (TapPositionC),
			"Control" : Control
			})

		link_name = self.name(regulator_id,"link")
		regulator_name = self.name(link_name,"regulator")
		sense_node = self.objects[link_name]["to"]
		self.assume(regulator_name,"sense_node",sense_node,f"regulator '{regulator_id}' does not specify sense node")
		return self.object("regulator", self.name(regulator_id,"link"), {
			"configuration" : configuration_name,
			"sense_node" : sense_node,
			})

def is_float(element):
	try:
		float(element)
		return True
	except ValueError:
		return False
def feeder_voltage_find(network_id):
	## set up feeder nominal voltage
	feeder_kVLN = 0.0
	if os.path.exists(os.path.join(input_folder,'feeder_map_2020.csv')): ## feeder_map_2020.csv should be provided from NG
		df_feeder_master = pd.read_csv(os.path.join(input_folder,'feeder_map_2020.csv'))
		df_feeder_select = df_feeder_master[df_feeder_master['GIS CDF'] == network_id].copy()
	for index, source in cyme_table["source"].iterrows():
		if source['NetworkId'] == network_id:
			if 'DesiredVoltage' in source.keys() and is_float(source['DesiredVoltage']) and float(source['DesiredVoltage'])>0:
				feeder_kVLN = round(float(source['DesiredVoltage'])/sqrt(3),3)
			elif 'EquipmentId' in source.keys() and is_float(source['EquipmentId'].split('_')[-1]) and float(source['EquipmentId'].split('_')[-1])>0:
				feeder_kVLN = round(float(source['EquipmentId'].split('_')[-1])/sqrt(3),3)
			elif os.path.exists(os.path.join(input_folder,'feeder_map_2020.csv')) and is_float(df_feeder_select['APS Voltage (kV)']) and float(df_feeder_select['APS Voltage (kV)'])>0:
				feeder_kVLN = round(float(df_feeder_select['APS Voltage (kV)'].iloc[0])/sqrt(3),3)
			break
	return feeder_kVLN

#
# CYME 5 MDB extractor
#
def cyme_extract_5020(network_id,network):

	creation_time = int(network["CreationTime"])
	last_change = int(network["LastChange"])
	load_factor = float(network["LoadFactor"])
	if single_file:
		glmname = os.path.abspath(f"{output_folder}/{cyme_mdbname}.glm")
	else:
		glmname = os.path.abspath(f"{output_folder}/{cyme_mdbname}_{network_id}.glm")

	glm = GLM(glmname,"w")
	glm.comment(
		f"Automatically generated by {git_project}/postproc/write_glm.py",
		)

	glm.blank()
	glm.comment("","Application information","")
	glm.define("APP_COMMAND",app_command)
	glm.define("APP_VERSION",app_version)

	glm.blank()
	glm.comment("","Git information","")
	glm.define("GIT_PROJECT",git_project)
	glm.define("GIT_COMMIT",git_commit)
	glm.define("GIT_BRANCH",git_branch)

	glm.blank()
	glm.comment("","GLM creation context","")
	glm.define("GLM_PATHNAME",glmname)
	glm.define("GLM_CREATED",dt.datetime.utcnow().isoformat())
	glm.define("GLM_USER",os.getenv("USER"))
	glm.define("GLM_WORKDIR",os.getenv("PWD"))
	glm.define("GLM_LANG",os.getenv("LANG"))

	# settings from model
	glm.blank()
	glm.comment("","CYME model information","")
	glm.define("CYME_MDBNAME",cyme_mdbname)
	glm.define("CYME_VERSION",version)
	glm.define("CYME_CREATED",dt.datetime.fromtimestamp(creation_time).isoformat())
	glm.define("CYME_MODIFIED",dt.datetime.fromtimestamp(last_change).isoformat())
	glm.define("CYME_LOADFACTOR",load_factor)
	glm.define("CYME_NETWORKID",network_id)

	# settings from config.csv
	glm.blank()
	glm.comment("","Settings from 'config.csv'","")
	define = settings["GLM_DEFINE"].split("=")
	if type(define) is list and len(define) > 1:
		glm.define(define[0].strip(),"=".join(define[1:]).strip())
	feeder_kVLN = feeder_voltage_find(network_id)
	if feeder_kVLN > 0:
		settings["GLM_NOMINAL_VOLTAGE"] = str(feeder_kVLN)+ ' kV'
		glm.define("GLM_NOMINAL_VOLTAGE",settings["GLM_NOMINAL_VOLTAGE"])
	elif settings["GLM_NOMINAL_VOLTAGE"]:
		glm.define("GLM_NOMINAL_VOLTAGE",settings["GLM_NOMINAL_VOLTAGE"])
	else:
		if settings["GLM_INCLUDE"]: # cannot verify setting in GLM_INCLUDE until run in gridlabd
			glm.ifndef("GLM_NOMINAL_VOLTAGE",lambda:glm.error("GLM_NOMINAL_VOLTAGE must be defined in either 'config.csv' or the GLM_INCLUDE file"))
		else:
			error("GLM_NOMINAL_VOLTAGE must be defined in either 'config.csv' or the GLM_INCLUDE file")
	if settings["GLM_INCLUDE"]:
		for include in settings["GLM_INCLUDE"].split():
			glm.include(include.strip())
	else:
		glm.blank()
		glm.comment("","default clock settings","")
		glm.clock({"timezone":"PST+8PDT", "starttime":"2020-01-01T00:00:00+08:00", "stoptime":"2020-01-01T00:05:00+08:00"})

	glm.blank()
	glm.comment("","Modules","")
	glm.module("powerflow",{"solver_method":"NR"})

	node_dict = {}
	device_dict = {}
	node_links = {}

	# cyme_table["node"] graph data
	if "nodetag" in cyme_table.keys():
		for index, node in table_find(cyme_table["nodetag"],NetworkId=network_id).iterrows():
			node_id = fix_name(node['NodeId'])
			node_dict[node_id] = [] # node dictionary
		for node_id, node in table_find(cyme_table["node"],NetworkId=network_id).iterrows():
			node_id = fix_name(node['NodeId'])
			node_links[node_id] = [] # incident links
	else:
		for index, node in table_find(cyme_table["node"],NetworkId=network_id).iterrows():
			node_id = fix_name(node['NodeId'])
			node_links[node_id] = [] # incident links
			node_dict[node_id] = [] # node dictionary

	glm.blank()
	glm.comment("","Objects","")

	# links
	for index, section in table_find(cyme_table["section"],NetworkId=network_id).iterrows():
		section_id = fix_name(section['SectionId'])
		links = glm.add("link",section_id,section, version=5020, node_links=node_links)
		if links:
			device_dict.update(links)

	# cyme_table["node"]
	for node_id in node_dict.keys():
		# only network node and substantiation will be added
		if table_find(cyme_table["node"],NodeId=node_id).iloc[0]["ComponentMask"] != "0":
			node_dict[node_id] = glm.add_node(node_id, node_links, device_dict, version=5020)

	# overhead lines
	try:
		for cyme_id, cyme_data in table_find(cyme_table["overheadbyphase"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("overhead_line_phase", cyme_id, cyme_data, version=5020)
	except:
		pass

	# unbalanced overhead lines
	try:
		for cyme_id, cyme_data in table_find(cyme_table["overheadlineunbalanced"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("overhead_line_unbalanced", cyme_id, cyme_data, version=5020)
	except:
		pass

	# overhead lines
	try:
		for cyme_id, cyme_data in table_find(cyme_table["overheadline"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("overhead_line", cyme_id, cyme_data, version=5020)
	except:
		pass

	# underground lines
	try:
		for cyme_id, cyme_data in table_find(cyme_table["undergroundline"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("underground_line", cyme_id, cyme_data, version=5020)
	except:
		pass

	# load
	for cyme_id, cyme_data in table_find(cyme_table["customerload"],NetworkId=network_id).iterrows():
		cyme_id = fix_name(cyme_data['DeviceNumber'])
		glm.add("load", cyme_id, cyme_data, version=5020, node_info={"Node_Links":node_links, "Device_Dicts": device_dict})

	# transformer
	for cyme_id, cyme_data in table_find(cyme_table["transformer"],NetworkId=network_id).iterrows():
		cyme_id = fix_name(cyme_data['DeviceNumber'])
		glm.add("transformer", cyme_id, cyme_data, version=4700)

	# transformerbyphase
	try:
		for cyme_id, cyme_data in table_find(cyme_table["transformerbyphase"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("single_transformer", cyme_id, cyme_data, version=5020)
	except:
		warning(f'{cyme_mdbname}@{network_id}: cannot add GLM objects from cyme_table "single_transformer".')

	# regulator
	try:
		for cyme_id, cyme_data in table_find(cyme_table["regulator"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("regulator", cyme_id, cyme_data, version=4700)
	except:
		warning(f'{cyme_mdbname}@{network_id}: cannot add GLM objects from cyme_table "regulator".')

	# cyme_table["capacitor"]
	for cyme_id, cyme_data in table_find(cyme_table["shuntcapacitor"],NetworkId=network_id).iterrows():
		glm.add("capacitor", cyme_id, cyme_data, version=5020,node_info={"Node_Links":node_links, "Device_Dicts": device_dict})

	# switches
	for cyme_id, cyme_data in table_find(cyme_table["switch"],NetworkId=network_id).iterrows():
		glm.add("switch", cyme_id, cyme_data, version=5020)

	# breaker
	try:
		for cyme_id, cyme_data in table_find(cyme_table["breaker"],NetworkId=network_id).iterrows():
			glm.add("breaker", cyme_id, cyme_data, version=5020)
	except:
		pass

	# recloser
	try:
		for cyme_id, cyme_data in table_find(cyme_table["recloser"],NetworkId=network_id).iterrows():
			glm.add("recloser", cyme_id, cyme_data, version=5020)
	except:
		pass

	# fuse
	try:
		for cyme_id, cyme_data in table_find(cyme_table["fuse"],NetworkId=network_id).iterrows():
			glm.add("fuse", cyme_id, cyme_data, version=5020)
	except:
		pass

	# check nade objects
	for name in list(glm.objects.keys()):
		data = glm.objects[name]
		if 'from' in data.keys() and data["from"] not in glm.objects.keys():
			node_dict[data["from"]] = glm.add_node(data["from"][3:], node_links, device_dict, version=5020)
		elif 'to' in data.keys() and data["to"] not in glm.objects.keys():
			node_dict[data["to"]] = glm.add_node(data["to"][3:], node_links, device_dict, version=5020)
		elif 'parent' in data.keys() and data["parent"] not in glm.objects.keys():
			node_dict[data["parent"]] = glm.add_node(data["parent"][3:], node_links, device_dict, version=5020)

	# collapse links
	done = False
	while not done:
		done = True
		for name in list(glm.objects.keys()):
			try:
				data = glm.objects[name]
				if "class" in data.keys() and data["class"] == "link": # needs to be collapse
					from_node = data["from"]
					to_node = data["to"]
					# while "parent" in glm.objects[to_node].keys() and glm.objects[glm.objects[to_node]["parent"]]["class"] == "node" \
					#   and to_node != glm.objects[to_node]["parent"]: # don't allow grandchild cyme_table["node"]
					# 	to_node = glm.objects[to_node]["parent"]
					# glm.objects[to_node]["parent"] = from_node
					glm.delete(name)
					done = False
					break
				elif "class" in data.keys() and data["class"] in ["node","load"] and "parent" in data.keys():
					parent_name = data["parent"]
					parent_data = glm.objects[parent_name]
					if "class" in parent_data.keys() and parent_data["class"] in ["node","load"] and "parent" in parent_data.keys():
						grandparent = parent_data["parent"]
						data["parent"] = grandparent
						done = False
						break
			except Exception as exc:
				warning(format_exception("link removal failed",name,glm.objects[name]))
				glm.delete(name)
				pass

	# remove extra connections between two node
	multi_g = nx.MultiGraph()
	for name in list(glm.objects.keys()):
		try:
			data = glm.objects[name]
			if "from" in data.keys() and "to" in data.keys():
				if data["from"] not in multi_g:
					multi_g.add_node(data["from"])
				if data["to"] not in multi_g:
					multi_g.add_node(data["to"])
				multi_g.add_edge(data["from"],data["to"],edge_name=name)
		except Exception as exc:
			warning(format_exception("connection removal failed",name,glm.objects[name]))
			glm.delete(name)
			pass
	for u in multi_g.nodes():
		for neighbor in multi_g.neighbors(u):
			if multi_g.number_of_edges(u,neighbor)>1:
				edge_data = {}
				for edge_id in multi_g[u][neighbor].keys():
					edge_data[multi_g[u][neighbor][edge_id]["edge_name"][0:2]] = edge_id
				# RG > TF > SW > OL
				if "RG" in edge_data.keys():
					# one of the multi-edges is regulator
					for key in edge_data.keys():
						if key != "RG":
							object_name = multi_g[u][neighbor][edge_data[key]]["edge_name"]
							if object_name in glm.objects.keys():
								glm.delete(object_name)
				elif "TF" in edge_data.keys():
					# one of the multi-edges is transformer
					for key in edge_data.keys():
						if key != "TF":
							object_name = multi_g[u][neighbor][edge_data[key]]["edge_name"]
							if object_name in glm.objects.keys():
								glm.delete(object_name)
				elif "SW" in edge_data.keys():
					# one of the multi-edges is switch
					for key in edge_data.keys():
						if key != "SW":
							object_name = multi_g[u][neighbor][edge_data[key]]["edge_name"]
							if object_name in glm.objects.keys():
								glm.delete(object_name)
				else:
					raise Exception(f"CYME model has unsupported duplicate connections between {u} and {neighbor}")
	# # check phase dismatch
	# for name in list(glm.objects.keys()):
	# 	data = glm.objects[name]
	# 	target_node_name = None
	# 	if "from" in data.keys() and "to" in data.keys():
	# 		target_node_name = data["to"]
	# 	elif "parent" in data.keys():
	# 		target_node_name = data["parent"]
	# 	if target_node_name:
	# 		target_node = glm.objects[target_node_name]
	# 		target_node_phases = target_node["phases"].replace("N","")
	# 		if data["phases"].replace("N","") != target_node_phases:
	# 			warning(f"phase dismatch: {target_node_name} has {target_node_phases} but {name} has {data['phases']}")
	#
	# Check conversion
	#
	for name, data in glm.objects.items():
		if not "name" in data.keys():
			warning("%s: object does not have a name, object data [%s]" % (glm.filename,data))
		elif not "class" in data.keys():
			warning("%s: object '%s' does not have a class" % (glm.filename,data["name"]))
		elif data["class"] in ["link","powerflow_object","line"]:
			print(glm.objects[name])
			warning("%s: object '%s' uses abstract-only class '%s'" % (glm.filename,data["name"],data["class"]))

	glm.close()

#
# CYME 4 MDB extractor ???
#
def cyme_extract_4700(network_id,network):
	creation_time = int(network["CreationTime"])
	last_change = int(network["LastChange"])
	load_factor = float(network["LoadFactor"])
	if single_file:
		glmname = os.path.abspath(f"{output_folder}/{cyme_mdbname}.glm")
	else:
		glmname = os.path.abspath(f"{output_folder}/{cyme_mdbname}_{network_id}.glm")

	glm = GLM(glmname,"w")
	glm.comment(
		f"Automatically generated by {git_project}/postproc/write_glm.py",
		)

	glm.blank()
	glm.comment("","Application information","")
	glm.define("APP_COMMAND",app_command)
	glm.define("APP_VERSION",app_version)

	glm.blank()
	glm.comment("","Git information","")
	glm.define("GIT_PROJECT",git_project)
	glm.define("GIT_COMMIT",git_commit)
	glm.define("GIT_BRANCH",git_branch)

	glm.blank()
	glm.comment("","GLM creation context","")
	glm.define("GLM_PATHNAME",glmname)
	glm.define("GLM_CREATED",dt.datetime.utcnow().isoformat())
	glm.define("GLM_USER",os.getenv("USER"))
	glm.define("GLM_WORKDIR",os.getenv("PWD"))
	glm.define("GLM_LANG",os.getenv("LANG"))

	# settings from model
	glm.blank()
	glm.comment("","CYME model information","")
	glm.define("CYME_MDBNAME",cyme_mdbname)
	glm.define("CYME_VERSION",version)
	glm.define("CYME_CREATED",dt.datetime.fromtimestamp(creation_time).isoformat())
	glm.define("CYME_MODIFIED",dt.datetime.fromtimestamp(last_change).isoformat())
	glm.define("CYME_LOADFACTOR",load_factor)
	glm.define("CYME_NETWORKID",network_id)

	# settings from config.csv
	glm.blank()
	glm.comment("","Settings from 'config.csv'","")
	define = settings["GLM_DEFINE"].split("=")
	if type(define) is list and len(define) > 1:
		glm.define(define[0].strip(),"=".join(define[1:]).strip())
	feeder_kVLN = feeder_voltage_find(network_id)
	if feeder_kVLN > 0:
		settings["GLM_NOMINAL_VOLTAGE"] = str(feeder_kVLN)+ ' kV'
		glm.define("GLM_NOMINAL_VOLTAGE",settings["GLM_NOMINAL_VOLTAGE"])
	elif settings["GLM_NOMINAL_VOLTAGE"]:
		glm.define("GLM_NOMINAL_VOLTAGE",settings["GLM_NOMINAL_VOLTAGE"])
	else:
		if settings["GLM_INCLUDE"]: # cannot verify setting in GLM_INCLUDE until run in gridlabd
			glm.ifndef("GLM_NOMINAL_VOLTAGE",lambda:glm.error("GLM_NOMINAL_VOLTAGE must be defined in either 'config.csv' or the GLM_INCLUDE file"))
		else:
			error("GLM_NOMINAL_VOLTAGE must be defined in either 'config.csv' or the GLM_INCLUDE file")
	if settings["GLM_INCLUDE"]:
		for include in settings["GLM_INCLUDE"].split():
			glm.include(include.strip())
	else:
		glm.blank()
		glm.comment("","default clock settings","")
		glm.clock({"timezone":"PST+8PDT", "starttime":"2020-01-01T00:00:00+08:00", "stoptime":"2020-01-01T00:05:00+08:00"})

	glm.blank()
	glm.comment("","Modules","")
	glm.module("powerflow",{"solver_method":"NR"})

	node_dict = {}
	device_dict = {}
	node_links = {}

	# cyme_table["node"] graph data
	if "nodetag" in cyme_table.keys():
		for index, node in table_find(cyme_table["nodetag"],NetworkId=network_id).iterrows():
			node_id = fix_name(node['NodeId'])
			node_dict[node_id] = [] # node dictionary
		for node_id, node in table_find(cyme_table["node"],NetworkId=network_id).iterrows():
			node_id = fix_name(node['NodeId'])
			node_links[node_id] = [] # incident links
	else:
		for index, node in table_find(cyme_table["node"],NetworkId=network_id).iterrows():
			node_id = fix_name(node['NodeId'])
			node_links[node_id] = [] # incident links
			node_dict[node_id] = [] # node dictionary

	glm.blank()
	glm.comment("","Objects","")

	# links
	for index, section in table_find(cyme_table["section"],NetworkId=network_id).iterrows():
		section_id = fix_name(section['SectionId'])
		links = glm.add("link",section_id,section, version=4700, node_links=node_links)
		if links:
			device_dict.update(links)

	# cyme_table["node"]
	for node_id in node_dict.keys():
		node_dict[node_id] = glm.add_node(node_id, node_links, device_dict, version=4700)

	# overhead lines
	try:
		for cyme_id, cyme_data in table_find(cyme_table["overheadline"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("overhead_line", cyme_id, cyme_data, version=4700)
	except:
		warning(f'{cyme_mdbname}@{network_id}: cannot add GLM objects from cyme_table "overheadline".')

	# underground lines
	try:
		for cyme_id, cyme_data in table_find(cyme_table["undergroundline"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("underground_line", cyme_id, cyme_data, version=4700)
	except:
		warning(f'{cyme_mdbname}@{network_id}: cannot add GLM objects from cyme_table "undergroundline".')

	# # load
	# for cyme_id, cyme_data in table_find(cyme_table["customerload"],NetworkId=network_id).iterrows():
	# 	cyme_id = fix_name(cyme_data['DeviceNumber'])
	# 	glm.add("load", cyme_id, cyme_data, version=4700, node_info={"Node_Links":node_links, "Device_Dicts": device_dict})

	# transformer
	for cyme_id, cyme_data in table_find(cyme_table["transformer"],NetworkId=network_id).iterrows():
		cyme_id = fix_name(cyme_data['DeviceNumber'])
		glm.add("transformer", cyme_id, cyme_data, version=4700)

	# regulator
	try:
		for cyme_id, cyme_data in table_find(cyme_table["regulator"],NetworkId=network_id).iterrows():
			cyme_id = fix_name(cyme_data['DeviceNumber'])
			glm.add("regulator", cyme_id, cyme_data, version=4700)
	except:
		warning(f'{cyme_mdbname}@{network_id}: cannot add GLM objects from cyme_table "regulator".')

	# capacitor
	for cyme_id, cyme_data in table_find(cyme_table["shuntcapacitor"],NetworkId=network_id).iterrows():
		cyme_id = fix_name(cyme_data['DeviceNumber'])
		glm.add("capacitor", cyme_id, cyme_data, version=4700,node_info={"Node_Links":node_links, "Device_Dicts": device_dict})

	# # switches
	# for cyme_id, cyme_data in table_find(cyme_table["switch"],NetworkId=network_id).iterrows():
	# 	glm.add("switch", cyme_id, cyme_data, version=5020)

	glm.close()


#
# Process cyme_table["network"]
#
cyme_extract = {
	"5020" : cyme_extract_5020, # CYME version 5 database
	"4700" : cyme_extract_4700, # CYME version 4 database
}
cyme_extract["-1"] = cyme_extract[str(default_cyme_extractor)]
network_count = 0
for index, network in cyme_table["network"].iterrows():
	network_id = network['NetworkId']
	if not re.match(settings["GLM_NETWORK_MATCHES"],network_id):
		continue
	else:
		network_count += 1
	if network_select != None and network_select != network_id:
		pass
	else:
		version = network["Version"]
		found = False
		for key, extractor in cyme_extract.items():
			if re.match(key,version):
				if version == "-1":
					warning(f"CYME model version is not specified (version=-1), using default extractor for version '{default_cyme_extractor}*'")
				extractor(network_id,network)
				found = True
		if not found:
			raise Exception(f"CYME model version {version} is not supported")

#
# Final checks
#

if network_count == 0:
	warning(f"  {cyme_mdbname}: the network pattern '{settings['GLM_NETWORK_MATCHES']}' did not match any networks in the database")
elif warning_count > 0:
	print("Model conversion problems can be corrected using 'GLM_MODIFY=modify.csv' in 'config.csv'.")
	print("  See http://docs.gridlabd.us/index.html?owner=openfido&project=cyme-extract&doc=/Post_processing/Write_glm.md for details")	

print(f"CYME-to-GridLAB-D conversion done: {network_count} networks processed, {warning_count} warnings, {error_count} errors")