#!/usr/bin/python3
app_version = 0

import sys, os
import subprocess
import glob
import datetime as dt
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from math import sqrt
import re
import hashlib
import csv

#
# Application information
#
app_command = os.path.abspath(sys.argv[0])
app_workdir = os.getenv("PWD")
app_path = "/"+"/".join(app_command.split("/")[0:-1])

#
# Git information
#
def command(cmd,lang="utf-8"):
	return subprocess.run(cmd.split(),stdout=subprocess.PIPE).stdout.decode(lang).strip()
os.chdir(app_path)
git_project = command("git config --local remote.origin.url")
git_commit = command("git rev-parse HEAD")
git_branch = command("git rev-parse --abbrev-ref HEAD")
os.chdir(app_workdir)

#
# CYME information
#
cyme_mdbname = os.getenv("PWD").split("/")[-1]

#
# Warning/error handling
#
def warning(*args):
	if settings["GLM_WARNINGS"] == "stdout":
		print("*** WARNING ***")
		print(" ","\n  ".join(args))
	elif settings["GLM_WARNINGS"] == "stderr":
		print("*** WARNING ***",file=sys.stderr)
		print(" ","\n  ".join(args),file=sys.stderr)
	else:
		raise Exception("\n".join(args))

def error(*args):
	if settings["GLM_ERRORS"] == "stdout":
		print("*** ERROR ***")
		print(" ","\n  ".join(args))
	elif settings["GLM_ERRORS"] == "stderr":
		print("*** ERROR ***",file=sys.stderr)
		print(" ","\n  ".join(args),file=sys.stderr)
	else:
		raise Exception("\n".join(args))

#
# Load user configuration ()
#
config = pd.DataFrame({
	"GLM_NETWORK_PREFIX" : ["network_"],
	"GLM_NETWORK_MATCHES" : [".*"],
	"GLM_NOMINAL_VOLTAGE" : [""],
	"GLM_INCLUDE" : [""],
	"GLM_DEFINE" : [""],
	"GLM_ERRORS" : ["exception"],
	"GLM_WARNINGS" : ["stdout"],
	"GLM_MODIFY" : ["modify.csv"],
	}).transpose().set_axis(["value"],axis=1,inplace=0)
config.index.name = "name" 
try:
	settings = pd.read_csv("../config.csv", dtype=str,
		names=["name","value"],
		comment = "#",
		).set_index("name")
	for name, values in settings.iterrows():
		if name in config.index:
			config["value"][name] = values[0]
except:
	pass
settings = config["value"]
print(f"Running write_glm.py:")
for name, data in config.iterrows():
	print(f"  {name} = {data['value']}")

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

	def __init__(self,file,mode):

		self.fh = open(file,mode)
		self.objects = {}

	def __del__(self):
		if self.object():
			self.error("glm object was deleted before objects were output")

	def name(self,name,oclass=None):
		if oclass:
			if not oclass in self.prefix.keys(): # name prefix not found
				prefix = f"Z{len(self.prefix.keys())}_"
				self.prefix[oclass] = prefix
				warning(f"{cyme_mdbname}:{network_id}: class '{oclass}' is not a known gridlabd powerflow class, using prefix '{prefix}' for names")
			else:
				prefix = self.prefix[oclass]
			name = prefix + name
		elif "0" <= name[0] <= "9":
			name = "_" + name
		return name.replace(" ","_")

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
			obj[key] = value
		obj["class"] = oclass
		return obj

	def modify(self,object,property,value):
		if type(value) is str:
			glm.write(f"modify {object}.{property} \"{value}\";")
		else:
			glm.write(f"modify {object}.{property} {value};")

	def close(self):
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
			for modify in settings["GLM_MODIFY"].split():
				self.blank()
				self.comment("",f"Modifications from '{modify}'","")
				if os.path.exists("../"+modify):
					with open("../"+modify,"r") as fh:
						reader = csv.reader(fh)
						for row in reader:
							if 0 < len(row) < 3:
								warning(f"{modify}: row '{','.join(list(row))}' is missing one or more required fields")
							elif len(row) > 3:
								warning(f"{modify}: row '{','.join(list(row))}' has extra fields that will be ignored")
								self.modify(*row[0:3])
							else:
								self.modify(*row)
			self.objects = {}

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
	8 : "breaker",
	10 : "recloser",
	12 : "sectionalizer",
	13 : "switch",
	14 : "fuse",
	17 : "capacitor",
	20 : "load",
	23 : "overhead_line",
}

#
# GLM databased construction tools
#

# find records in a table (exact field match only)
def table_find(table,**kwargs):
	result = table
	for key,value in kwargs.items():
		result = result[result[key]==value]
	return result

# get the value in a table using the index
def table_get(table,id,column=0):
	return table.loc[id][column]

# add a link to glm file
def add_link(section_id,section):
	phase = int(section["Phase"])
	from_node_id = section["FromNodeId"]
	to_node_id = section["ToNodeId"]
	device_dict = {}
	for device_id, device in table_find(sectiondevices,SectionId=section_id).iterrows():
		device_type = int(device["DeviceType"])
		if device_type in glm_devices.keys():
			device_name = glm.name(device_id,"link")
			device_dict[device_id] = glm.object("link", device_name , {
				"phases" : cyme_phase_name[phase],
				"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
				"from" : glm.name(from_node_id,"node"),
				"to" : glm.name(to_node_id,"node"),
				})
			node_links[from_node_id].append(device_id)
			node_links[to_node_id].append(device_id)
		else:
			warning(
				f"{cyme_mdbname}@{network_id}: device {device_id}: device type {device_type} ({cyme_devices[device_type]}) has no corresponding GLM object",
				f"{cyme_mdbname}@{network_id}: omitting device {device_id} is likely to change the results and/or cause solver issues",
				)
	return device_dict

# add node to glm file
def add_node(node_id,node_links,device_dict):
	phase = 0
	for device_id in node_links[node_id]:
		phase |= glm_phase_code[device_dict[device_id]["phases"]]
	obj = glm.object("node", glm.name(node_id,"node"), {
		"phases" : glm_phase_name[phase],
		"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
		})
	if node_id == head_node:
		obj["bustype"] = "SWING"
	else:
		obj["bustype"] = "PQ"
	return obj

# add an overhead based on a link
def add_overhead_line(line_id,line):
	line_name = glm.name(line_id,"link")
	length = float(line["Length"])
	conductorA_id = line["PhaseConductorIdA"]
	conductorB_id = line["PhaseConductorIdB"]
	conductorC_id = line["PhaseConductorIdC"]
	conductorN_id = line["NeutralConductorId"]
	add_overhead_line_conductors([conductorA_id,conductorB_id,conductorC_id,conductorN_id])
	spacing_id = line["ConductorSpacingId"]
	add_line_spacing(spacing_id)
	configuration_name = add_line_configuration([conductorA_id,conductorB_id,conductorC_id,conductorN_id,spacing_id])
	return glm.object("overhead_line", line_name, {
		"length" : "%.2f m"%length,
		"configuration" : configuration_name,
		})

# add an unbalanced overhead line based on a link
def add_overhead_line_unbalanced(line_id,line):
	line_name = glm.name(line_id,"link")
	configuration_id = line["LineId"]
	configuration_name = glm.name(configuration_id,"line_configuration")
	length = float(line["Length"])
	if not configuration_name in glm.objects.keys():
		configuration = eqoverheadlineunbalanceds.loc[configuration_id]
		conductorA_id = configuration["PhaseConductorIdA"]
		conductorB_id = configuration["PhaseConductorIdB"]
		conductorC_id = configuration["PhaseConductorIdC"]
		conductorN_id = configuration["NeutralConductorId"]
		conductor_names = add_overhead_line_conductors([conductorA_id,conductorB_id,conductorC_id,conductorN_id])
		spacing_id = configuration["ConductorSpacingId"]
		spacing_name = add_line_spacing(spacing_id)
		glm.object("line_configuration",configuration_name,{
			"conductor_A" : conductor_names[0],
			"conductor_B" : conductor_names[1],
			"conductor_C" : conductor_names[2],
			"conductor_N" : conductor_names[3],
			"spacing" : spacing_name,
			})
	return glm.object("overhead_line", line_name, {
		"length" : "%.2f m"%length,
		"configuration" : configuration_name,
		})

# add overhead line conductor library entry
def add_overhead_line_conductors(conductors):
	conductor_names = []
	for conductor_id in conductors:
		conductor_name = glm.name(conductor_id,"overhead_line_conductor")
		if not conductor_name in glm.objects.keys():
			conductor = eqconductors.loc[conductor_id]
			gmr = float(conductor["GMR"])
			r25 = float(conductor["R25"])
			diameter = float(conductor["Diameter"])
			nominal_rating = float(conductor["NominalRating"])
			obj = glm.object("overhead_line_conductor",conductor_name,{
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
def add_line_spacing(spacing_id):
	spacing_name = glm.name(spacing_id,"line_spacing")
	if not spacing_name in glm.objects.keys():
		spacing = eqgeometricalarrangements.loc[spacing_id]
		Ax = float(spacing["ConductorA_Horizontal"])
		Ay = float(spacing["ConductorA_Vertical"])
		Bx = float(spacing["ConductorA_Horizontal"])
		By = float(spacing["ConductorA_Vertical"])
		Cx = float(spacing["ConductorA_Horizontal"])
		Cy = float(spacing["ConductorA_Vertical"])
		Nx = float(spacing["NeutralConductor_Horizontal"])
		Ny = float(spacing["NeutralConductor_Vertical"])
		ABx = Ax-Bx; ABy = Ay-By
		ACx = Ax-Cx; ACy = Ay-Cy
		BCx = Bx-Cx; BCy = By-Cy
		ANx = Ax-Nx; ANy = Ay-Ny
		BNx = Bx-Nx; BNy = By-Ny
		CNx = Cx-Nx; CNy = Cy-Ny
		glm.object("line_spacing",spacing_name,{
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
def add_line_configuration(items):
	configuration_id = "_".join(items)
	configuration_name = glm.name(configuration_id,"line_configuration")
	if not configuration_name in glm.objects.keys():
		glm.object("line_configuration",configuration_name,{
			"conductor_A" : glm.name(items[0],"overhead_line_conductor"),
			"conductor_B" : glm.name(items[1],"overhead_line_conductor"),
			"conductor_C" : glm.name(items[2],"overhead_line_conductor"),
			"conductor_N" : glm.name(items[3],"overhead_line_conductor"),
			"spacing" : glm.name(items[4],"line_spacing")
			})
	return configuration_name

# get the phase switch status
def get_switch_phase_status(phases,state):
	if state in phases:
		return "CLOSED"
	else:
		return "OPEN"

# add a switch based on a link
def add_switch(switch_id,switch):
	switch_name = glm.name(switch_id,"link")
	phases = cyme_phase_name[int(switch["ClosedPhase"])]
	return glm.object("switch", switch_name, {
		"phase_A_state" : get_switch_phase_status(phases,"A"),
		"phase_B_state" : get_switch_phase_status(phases,"B"),
		"phase_C_state" : get_switch_phase_status(phases,"C"),
		"operating_mode" : "BANKED"
		})

# add a load
def add_load(load_id,load):
	section_id = table_get(sectiondevices,load_id,"SectionId")
	section_name = glm.name(section_id,"load")
	DeviceType = int(load["DeviceType"])
	phase = cyme_phase_name[int(load["Phase"])]
	if DeviceType in glm_devices.keys():
		ConsumerClassId = load["ConsumerClassId"]
		LoadValue1 = float(load["LoadValue1"])
		LoadValue2 = float(load["LoadValue2"])
		load_types = {"Z":"constant_impedance","I":"constant_current","P":"constant_power"}
		if ConsumerClassId in load_types.keys():
			return glm.object("load",section_name,{
				"parent" : glm.name(section_id,"node"),
				"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
				f"{load_types[ConsumerClassId]}_{phase}" : "%.4g%+.4gj" % (LoadValue1,LoadValue2),
				})
		elif ConsumerClassId in ["PQ","PV","SWING","SWINGPQ"]: # GLM bus types allowed
			return glm.object("load",section_name,{
				"parent" : glm.name(section_id,"node"),
				"nominal_voltage" : "${GLM_NOMINAL_VOLTAGE}",
				"bustype" : ConsumerClassId,
				f"constant_impedance_{phase}" : "%.4g%+.4gj" % (LoadValue1,LoadValue2),
				})
	else:
		warning(f"{cyme_mdbname}@{network_id}: load '{load_id}' on phase '{phase}' dropped because '{cyme_devices[DeviceType]}' is not a supported CYME device type")

# add a capacitor
def add_capacitor(capacitor_id,capacitor):
	capacitor_name = glm.name(capacitor_id,"capacitor")
	phase = cyme_phase_name[int(capacitor["Phase"])]
	KVARA = float(capacitor["KVARA"])
	KVARB = float(capacitor["KVARB"])
	KVARC = float(capacitor["KVARC"])
	KVLN = float(capacitor["KVLN"])
	return glm.object("capacitor",capacitor_name,{
		"parent" : glm.name(capacitor_id,"node"),
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
def add_transformer(transformer_id, transformer):
	warning(f"{cyme_mdbname}@{network_id}: unable to convert transformer '{transformer_id}' using data {transformer.to_dict()}")
	# DeviceType = int(transformer["DeviceType"])
	# equipment_id = transformer["EquipmentId"]
	# equipment = eqtransformers.loc[equipment_id]
	# NominalRatingKVA = float(equipment["NominalRatingKVA"])
	# PrimaryVoltageKVLL = float(equipment["PrimaryVoltageKVLL"])
	# SecondaryVoltageKVLL = float(equipment["SecondaryVoltageKVLL"])
	# if PrimaryVoltageKVLL == SecondaryVoltageKVLL:
	# 	SecondaryVoltageKVLL += 0.001
	# 	warning(f"{cyme_mdbname}@{network_id}: transformer {transformer_id} PrimaryVoltageKVLL = SecondaryVoltageKVLL, adjusting SecondaryVoltageKVLL by 1V")
	# PosSeqImpedancePercent = float(equipment["PosSeqImpedancePercent"])
	# XRRatio = float(equipment["XRRatio"])
	# if XRRatio == 0.0:
	# 	r = 0.000333
	# 	x = 0.00222
	# 	warning(f"{cyme_mdbname}@{network_id}:  transformer {transformer_id} XRRatio is zero, using default impedance {'%.4g%+.4gj' % (r,x)}")
	# else:
	# 	r = XRRatio / 100.0 / sqrt(1+XRRatio**2)
	# 	x = r * XRRatio
	# nominal_rating = "%.4g kVA" % (NominalRatingKVA)
	# primary_voltage = "%.4g kV" % (PrimaryVoltageKVLL/sqrt(3.0))
	# secondary_voltage = "%.4g kV" % (SecondaryVoltageKVLL/sqrt(3.0))
	# configuration_name = glm.name("transformer_configuration_")
	# impedance = "%.4g%+.4gj" % (r,x)
	# configuration_name = glm.name(configuration,)
	# return glm.object("transformer_configure",transformer_id,{
	# 	"NominalRatingKVA" : ,
	# 	"PrimaryRatedCapacity" : , primary_voltage
	# 	"SecondaryRatedCapacity" : secondary_voltage,
	# 	"impedance" : "%.4g%+.4gj" % (r,x),
	# 	})
	return

# add a regulator
def add_regulator(regulator_id, regulator):
	return

#
# Load all the model tables (table names have an "s" appended)
#
for filename in glob.iglob("*.csv"):
	data = pd.read_csv(filename, dtype=str)
	name = filename[0:-4]
	index = data.columns[0]
	globals()[name+"s"] = data.set_index(index)

#
# Process networks
#
network_count = 0
for network_id, network in networks.iterrows():
	
	if not re.match(settings["GLM_NETWORK_MATCHES"],network_id):
		continue
	else:
		network_count += 1

	version = network["Version"]
	creation_time = int(network["CreationTime"])
	last_change = int(network["LastChange"])
	load_factor = float(network["LoadFactor"])
	head_node = table_get(headnodes,network_id)
	glmname = os.path.abspath(f"../{settings['GLM_NETWORK_PREFIX']}{network_id}.glm")

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

	# nodes graph data
	for node_id, node in table_find(nodes,NetworkId=network_id).iterrows():
		node_links[node_id] = [] # incident links
		node_dict[node_id] = [] # node dictionary

	glm.blank()
	glm.comment("","Objects","")

	# links
	for section_id, section in table_find(sections,NetworkId=network_id).iterrows():
		device_dict.update(add_link(section_id,section))

	# nodes
	for node_id in node_dict.keys():
		node_dict[node_id] = add_node(node_id,node_links,device_dict)

	# overhead lines
	for line_id, line in table_find(overheadbyphases,NetworkId=network_id).iterrows():
		add_overhead_line(line_id,line)

	# unbalanced overhead lines
	for line_id, line in table_find(overheadlineunbalanceds,NetworkId=network_id).iterrows():
		add_overhead_line_unbalanced(line_id,line)

	# loads
	for load_id, load in table_find(customerloads,NetworkId=network_id).iterrows():
		add_load(load_id,load)

	# transformers
	for transformer_id, transformer in table_find(transformers,NetworkId=network_id).iterrows():
		add_transformer(transformer_id,transformer)

	# regulators
	for regulator_id, regulator in table_find(regulators,NetworkId=network_id).iterrows():
		add_transformer(regulator_id,regulator)

	# capacitors
	for cap_id, cap in table_find(shuntcapacitors,NetworkId=network_id).iterrows():
		add_capacitor(cap_id,cap)

	# switches
	for switch_id, switch in table_find(switchs,NetworkId=network_id).iterrows():
		add_switch(switch_id,switch)

	glm.close()

if network_count == 0:
	warning(f"  {cyme_mdbname}: the network pattern '{settings['GLM_NETWORK_MATCHES']}' did not match any networks in the database")
