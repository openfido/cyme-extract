#!/usr/bin/python3
"""OpenFIDO write_glm post-processor script

Syntax:
	host% python3 -m write_glm.py -i|--input INPUTDIR -o|--output OUTPUTDIR -d|--data DATADIR [-c|--config [CONFIGCSV]] [-h|--help] [-t|--cyme-tables]

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
from math import sqrt
from math import cos
from math import sin
from math import pi
import re
import hashlib
import csv
import pprint
pp = pprint.PrettyPrinter(indent=4,compact=True)
import traceback
from copy import copy

#
# Required tables to operate properly
#
cyme_tables_required = [
	"CYMNETWORK","CYMHEADNODE","CYMNODE","CYMSECTION","CYMSECTIONDEVICE",
	"CYMOVERHEADBYPHASE","CYMOVERHEADLINEUNBALANCED","CYMEQCONDUCTOR",
	"CYMEQGEOMETRICALARRANGEMENT","CYMEQOVERHEADLINEUNBALANCED",
	"CYMSWITCH","CYMCUSTOMERLOAD","CYMLOAD","CYMSHUNTCAPACITOR",
	"CYMTRANSFORMER","CYMEQTRANSFORMER","CYMREGULATOR","CYMEQREGULATOR"
	]


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
opts, args = getopt.getopt(sys.argv[1:],"hc:i:o:d:t",["help","config=","input=","output=","data=","cyme-tables"])

def help(exit_code=None,details=False):
	print("Syntax: python3 -m write_glm.py -i|--input DIR -o|--output DIR -d|--data DIR [-h|--help] [-t|--cyme-tables] [-c|--config CSV]")
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
default_cyme_extractor = "50"

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
	"GLM_ASSUMPTIONS" : ["include"]
	}).transpose().set_axis(["value"],axis=1,inplace=0)
config.index.name = "name" 
settings = pd.read_csv(config_file, dtype=str,
	names=["name","value"],
	comment = "#",
	).set_index("name")
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
	# 8 : "breaker",
	# 10 : "recloser",
	# 12 : "sectionalizer",
	13 : "switch",
	# 14 : "fuse",
	17 : "capacitor",
	20 : "load",
	21 : "load",
	23 : "overhead_line",
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

# get the value in a table using the index
def table_get(table,id,column=None):
	if column == None or column == "*":
		return table.loc[id]
	else:
		return table.loc[id][column]

def load_cals(load_type,load_phase,connection,load_power1,load_power2):
	phase_number=int(load_phase)
	# default_model_voltage in kV
	if connection == 0: # wye connecttion
		vol_real = float(default_model_voltage)*cos((1-phase_number)*pi*2.0/3.0)*1000.0
		vol_imag = float(default_model_voltage)*sin((1-phase_number)*pi*2.0/3.0)*1000.0
		line_phase_gain = 1
	elif connection == 2: # delta connection
		vol_real = float(default_model_voltage)*cos((1-phase_number)*pi*2.0/3.0+pi/6.0)*1000.0
		vol_imag = float(default_model_voltage)*sin((1-phase_number)*pi*2.0/3.0+pi/6.0)*1000.0
		line_phase_gain = sqrt(3.0)
	else:
		error("wrong connection type")
	vol_mag = float(default_model_voltage)*1000
	vol_complex = vol_real+vol_imag*(1j)
	if load_type == "Z":
		load_cals_results = vol_mag*line_phase_gain*vol_mag*line_phase_gain/(load_power1+load_power2*(1j))
		return load_cals_results
	elif load_type == "I":
		load_cals_results  = (load_power1+load_power2*(1j))/(vol_complex*line_phase_gain)
		return load_cals_results	
	else:
		# for constant power load, the imag part is negative
		load_cals_results = load_power1-load_power2*(1j)
		return load_cals_results

#
# Load all the model tables (table names have an "s" appended)
#
cyme_table = {}
for filename in glob.iglob(f"{data_folder}/*.csv"):
	data = pd.read_csv(filename, dtype=str)
	index = data.columns[0]
	name = os.path.basename(filename)[0:-4].lower()
	cyme_table[name] = data.set_index(index)
for filename in cyme_tables_required:
	if filename[3:].lower() not in cyme_table.keys():
		raise Exception(f"required CYME table '{filename}' is not found in {input_folder}")

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
		"overhead_line" : "OL",
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
		return name.replace(" ","_") # remove white spaces from names

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
			with open(f"{input_folder}/{modify}","r") as fh:
				reader = csv.reader(fh)
				for row in reader:
					if 0 < len(row) < 3:
						warning(f"{modify}: row '{','.join(list(row))}' is missing one or more required fields")
					elif len(row) > 3:
						warning(f"{modify}: row '{','.join(list(row))}' has extra fields that will be ignored")
						self.modify(*row[0:3])
					else:
						self.modify(*row)

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
		from_node_id = section["FromNodeId"]
		to_node_id = section["ToNodeId"]
		device_dict = {}
		for device_id, device in table_find(cyme_table["sectiondevice"],SectionId=section_id).iterrows():
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
		return device_dict

	# add node to glm file
	def add_node(self,node_id,node_links,device_dict,version):
		phase = 0
		for device_id in node_links[node_id]:
			phase |= glm_phase_code[device_dict[device_id]["phases"]]
		obj = self.object("node", self.name(node_id,"node"), {
			"phases" : glm_phase_name[phase]+"N",
			"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
			})
		if node_id == table_get(cyme_table["headnode"],network_id,"NodeId"):
			obj["bustype"] = "SWING"
		else:
			obj["bustype"] = "PQ"
		return obj

	# add an overhead based on a link
	def add_overhead_line(self,line_id,line,version):
		line_name = self.name(line_id,"link")
		length = float(line["Length"])
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
		if not configuration_name in self.objects.keys():
			configuration = cyme_table["eqoverheadlineunbalanced"].loc[configuration_id]
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

	# add overhead line conductor library entry
	def add_overhead_line_conductors(self,conductors,version):
		conductor_names = []
		for conductor_id in conductors:
			conductor_name = self.name(conductor_id,"overhead_line_conductor")
			if not conductor_name in self.objects.keys():
				conductor = cyme_table["eqconductor"].loc[conductor_id]
				gmr = float(conductor["GMR"])
				r25 = float(conductor["R25"])
				diameter = float(conductor["Diameter"])
				nominal_rating = float(conductor["NominalRating"])
				# should set up NONE conductor rating as non-zero value
				# cannot use modify.csv to change the ratings fior OC_NONE
				if nominal_rating == 0:
					nominal_rating = 1000				
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
			spacing = cyme_table["eqgeometricalarrangement"].loc[spacing_id]
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

	# get the phase switch status
	def get_switch_phase_status(self,phases,state):
		if state in phases:
			return "CLOSED"
		else:
			return "OPEN"

	# add a switch based on a link
	def add_switch(self,switch_id,switch,version):
		switch_name = self.name(switch_id,"link")
		phases = cyme_phase_name[int(switch["ClosedPhase"])]
		return self.object("switch", switch_name, {
			"phase_A_state" : self.get_switch_phase_status(phases,"A"),
			"phase_B_state" : self.get_switch_phase_status(phases,"B"),
			"phase_C_state" : self.get_switch_phase_status(phases,"C"),
			"operating_mode" : "BANKED"
			})

	# add a load
	def add_load(self,load_id,load,version):
		section_id = table_get(cyme_table["sectiondevice"],load_id,"SectionId")
		section = table_get(cyme_table["section"],section_id)
		device_type = int(table_get(cyme_table["sectiondevice"],load_id,"DeviceType"))
		connection_type = int(table_get(cyme_table["load"],load_id,"ConnectionConfiguration"))
		if device_type == 20: # spot load is attached at from node of section
			parent_name = self.name(section["FromNodeId"],"node")
		elif device_type == 21: # distributed load is attached at to node of section
			parent_name = self.name(section["ToNodeId"],"node")
		else:
			raise Exception(f"CYME device type {device_type} is not supported as a load")
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
			load_value1 = float(load["LoadValue1"]) * 1000
			load_value2 = float(load["LoadValue2"]) * 1000
			# from the mdb file, type for constant power load is defined as PQ
			load_types = {"Z":"constant_impedance","I":"constant_current","PQ":"constant_power"}
			if ConsumerClassId in load_types.keys() and (load_value1*load_value1+load_value2*load_value2) > 0:
				load_cals_complex = load_cals(ConsumerClassId,load["Phase"],connection_type,load_value1,load_value2)
				load_value1 = load_cals_complex.real
				load_value2 = -load_cals_complex.imag
				return self.object("load",load_name,{
					"parent" : parent_name,
					"phases" : phases,
					"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
					f"{load_types[ConsumerClassId]}_{phase}" : "%.4g%+.4gj" % (load_value1,load_value2),
					})
			elif ConsumerClassId in ["PV","SWING","SWINGPQ"] and (load_value1*load_value1+load_value2*load_value2) > 0: # GLM bus types allowed
				load_cals_complex = load_cals("Z",load["Phase"],connection_type,load_value1,load_value2)
				load_value1 = load_cals_complex.real
				load_value2 = -load_cals_complex.imag
				return self.object("load",load_name,{
					"parent" : parent_name,
					"phases" : phases,
					"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
					"bustype" : ConsumerClassId,
					f"constant_impedance_{phase}" : "%.4g%+.4gj" % (load_value1,load_value2),
					})
		else:
			warning(f"{cyme_mdbname}@{network_id}: load '{load_id}' on phase '{phase}' dropped because '{cyme_devices[device_type]}' is not a supported CYME device type")

	# add a capacitor
	def add_capacitor(self,capacitor_id,capacitor,version):
		section_id = table_get(cyme_table["sectiondevice"],capacitor_id,"SectionId")
		section = table_get(cyme_table["section"],section_id)
		from_name = self.name(section["FromNodeId"],"node")
		to_name = self.name(section["ToNodeId"],"node")

		link_name = self.name(capacitor_id,"link")
		if link_name in self.objects.keys(): # link is no longer needed
			self.delete(link_name)
		
		capacitor_name = self.name(capacitor_id,"capacitor")
		phase = cyme_phase_name[int(capacitor["Phase"])]
		KVARA = float(capacitor["KVARA"])
		KVARB = float(capacitor["KVARB"])
		KVARC = float(capacitor["KVARC"])
		KVLN = float(capacitor["KVLN"])
		switchA = "CLOSED"
		self.assume(capacitor_name,"switchA",switchA,f"capacitor {capacitor_id} does not specify switch A position, valid options are 'CLOSED' or 'OPEN'")
		switchB = "CLOSED"
		self.assume(capacitor_name,"switchB",switchB,f"capacitor {capacitor_id} does not specify switch B position, valid options are 'CLOSED' or 'OPEN'")
		switchC = "CLOSED"
		self.assume(capacitor_name,"switchC",switchC,f"capacitor {capacitor_id} does not specify switch C position, valid options are 'CLOSED' or 'OPEN'")
		control = "MANUAL"
		self.assume(capacitor_name,"control",control,f"capacitor {capacitor_id} does not specify a control strategy, valid options are 'CURRENT', 'VARVOLT', 'VOLT', 'VAR', or 'MANUAL'")
		return self.object("capacitor",capacitor_name,{
			"parent" : from_name,
			"nominal_voltage" : f"{KVLN} kV",
			"phases" : phase,
			"phases_connected" : phase,
			"capacitor_A" : f"{KVARA} kVA",
			"capacitor_B" : f"{KVARB} kVA",
			"capacitor_C" : f"{KVARC} kVA",
			"switchA" : "CLOSED",
			"switchB" : "CLOSED",
			"switchC" : "CLOSED",
			"control" : "MANUAL",
			})

	# add a transformer
	def add_transformer(self,transformer_id, transformer,version):
		DeviceType = int(transformer["DeviceType"])
		equipment_id = transformer["EquipmentId"]
		equipment = cyme_table["eqtransformer"].loc[equipment_id]
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
		link_name = self.name(transformer_id,"link")
		return self.object("transformer", link_name, {
			"nominal_voltage" : None,
			"phases" : "".join(sorted(set(self.objects[link_name]["phases"] + "N"))),
			"configuration" : configuration_name,
			})

	# add a regulator
	def add_regulator(self, regulator_id, regulator, version):
		equipment_id = regulator["EquipmentId"]
		equipment = cyme_table["eqregulator"].loc[equipment_id]

		CTPrimaryRating = float(regulator["CTPrimaryRating"])
		PTRatio = float(regulator["PTRatio"])
		BandWidth = float(regulator["BandWidth"])
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
		configuration_name = self.name([band_width,time_delay],"regulator_configuration")
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
			"regulation" : "%.1f%%" % (BandWidth / (RatedKVLN*1000) * 100),
			"tap_pos_A" : "%.0f" % (TapPositionA),
			"tap_pos_B" : "%.0f" % (TapPositionB),
			"tap_pos_C" : "%.0f" % (TapPositionC),
			"Control" : Control
			})

		link_name = self.name(regulator_id,"link")
		regulator_name = self.name(regulator_id,"regulator")
		sense_node = self.objects[link_name]["to"]
		self.assume(link_name,"sense_node",sense_node,f"regulator '{regulator_id}' does not specify sense node")
		return self.object("regulator", self.name(regulator_id,"link"), {
			"configuration" : configuration_name,
			"sense_node" : sense_node,
			})

#
# CYME 5 MDB extractor
#
def cyme_extract_5020(network_id,network):

	creation_time = int(network["CreationTime"])
	last_change = int(network["LastChange"])
	load_factor = float(network["LoadFactor"])
	glmname = os.path.abspath(f"{output_folder}/{cyme_mdbname}_{network_id}.glm")

	glm = GLM(glmname,"w")
	glm.comment(
		f"Automatically generated by {git_project.replace('.git','/postproc/write_glm.py')}",
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
	if settings["GLM_NOMINAL_VOLTAGE"]:
		glm.define("GLM_NOMINAL_VOLTAGE",settings["GLM_NOMINAL_VOLTAGE"])
	for include in settings["GLM_INCLUDE"].split():
		glm.include(include.strip())
	if not settings["GLM_NOMINAL_VOLTAGE"]:
		if settings["GLM_INCLUDE"]: # cannot verify setting in GLM_INCLUDE until run in gridlabd
			glm.ifndef("GLM_NOMINAL_VOLTAGE",lambda:glm.error("GLM_NOMINAL_VOLTAGE must be defined in either 'config.csv' or the GLM_INCLUDE file"))
		else:
			error("GLM_NOMINAL_VOLTAGE must be defined in either 'config.csv' or the GLM_INCLUDE file")

	glm.blank()
	glm.comment("","Modules","")
	glm.module("powerflow",{"solver_method":"NR"})

	node_dict = {}
	device_dict = {}
	node_links = {}

	# cyme_table["node"] graph data
	for node_id, node in table_find(cyme_table["node"],NetworkId=network_id).iterrows():
		node_links[node_id] = [] # incident links
		node_dict[node_id] = [] # node dictionary

	glm.blank()
	glm.comment("","Objects","")

	# links
	for section_id, section in table_find(cyme_table["section"],NetworkId=network_id).iterrows():
		links = glm.add("link",section_id,section, version=5020, node_links=node_links)
		if links:
			device_dict.update(links)

	# cyme_table["node"]
	for node_id in node_dict.keys():
		# only network node and substantiation will be added
		if table_get(cyme_table["node"],node_id,"ComponentMask") != "0":
			node_dict[node_id] = glm.add_node(node_id, node_links, device_dict, version=5020)

	# overhead lines
	for cyme_id, cyme_data in table_find(cyme_table["overheadbyphase"],NetworkId=network_id).iterrows():
		glm.add("overhead_line", cyme_id, cyme_data, version=5020)

	# unbalanced overhead lines
	for cyme_id, cyme_data in table_find(cyme_table["overheadlineunbalanced"],NetworkId=network_id).iterrows():
		glm.add("overhead_line_unbalanced", cyme_id, cyme_data, version=5020)

	# cyme_table["load"]
	for cyme_id, cyme_data in table_find(cyme_table["customerload"],NetworkId=network_id).iterrows():
		glm.add("load", cyme_id, cyme_data, version=5020)

	# cyme_table["transformer"]
	for cyme_id, cyme_data in table_find(cyme_table["transformer"],NetworkId=network_id).iterrows():
		glm.add("transformer", cyme_id, cyme_data, version=5020)

	# cyme_table["regulator"]
	for cyme_id, cyme_data in table_find(cyme_table["regulator"],NetworkId=network_id).iterrows():
		glm.add("regulator", cyme_id, cyme_data, version=5020)

	# cyme_table["capacitor"]
	for cyme_id, cyme_data in table_find(cyme_table["shuntcapacitor"],NetworkId=network_id).iterrows():
		glm.add("capacitor", cyme_id, cyme_data, version=5020)
	# switches
	for cyme_id, cyme_data in table_find(cyme_table["switch"],NetworkId=network_id).iterrows():
		glm.add("switch", cyme_id, cyme_data, version=5020)

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
					while "parent" in glm.objects[to_node].keys() and glm.objects[to_node]["parent"]["class"] == "node": # don't allow grandchild cyme_table["node"]
						to_node = glm.objects[to_node]["parent"]
					glm.objects[to_node]["parent"] = from_node
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

	#
	# Check conversion
	#
	for name, data in glm.objects.items():
		if not "name" in data.keys():
			warning("%s: object does not have a name, object data [%s]" % (glm.filename,data))
		elif not "class" in data.keys():
			warning("%s: object '%s' does not have a class" % (glm.filename,data["name"]))
		elif data["class"] in ["link","powerflow_object","line"]:
			warning("%s: object '%s' uses abstract-only class '%s'" % (glm.filename,data["name"],data["class"]))

	glm.close()

#
# Process cyme_table["network"]
#
cyme_extract = {
	"50" : cyme_extract_5020, # CYME version 5 database
}
cyme_extract["-1"] = cyme_extract[str(default_cyme_extractor)]
network_count = 0
for network_id, network in cyme_table["network"].iterrows():
	
	if not re.match(settings["GLM_NETWORK_MATCHES"],network_id):
		continue
	else:
		network_count += 1

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
