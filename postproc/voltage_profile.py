#!/usr/bin/python3
import sys, os, time
import json 
import getopt
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import math
import numpy as np

input_folder = None
output_folder = None
data_folder = None
config_file = None
equipment_file = None
network_select = None
single_file = False
generated_file = None
WARNING = True
DEBUG = False
QUIET = False
VERBOSE = False

opts, args = getopt.getopt(sys.argv[1:],"hc:i:o:d:tn:e:g:C:",["help","config=","input=","output=","data=","cyme-tables","network_ID=","equipment_file=","generated=","coordinate="])

#
# Warning/error/help handling
#
def help(exit_code=None,details=False):
	print("Syntax: python3 -m voltage_profile.py -i|--input DIR -o|--output DIR -d|--data DIR [-h|--help] [-g|--generated 'file name'][-t|--cyme-tables] [-c|--config CSV] [-e|--equipment 'file name'] [-n|--network_ID 'ID1 ID2 ..']  [-C|-coodinate CSV]")
	if details:
		print(globals()[__name__].__doc__)
	if type(exit_code) is int:
		exit(exit_code)

def verbose(msg):
	print(f"VERBOSE [voltage_profile] {msg}",flush=True)

warning_count = 0
warning_file = sys.stderr
def warning(msg):
	global warning_count
	warning_count += 1
	if WARNING:
		print(f"WARNING [voltage_profile] {msg}",file=warning_file,flush=True)
	if VERBOSE:
		verbose(msg)

error_count = 0
error_file = sys.stderr
def error(msg,code=None):
	global error_count
	error_count += 1
	if DEBUG:
		raise Exception(msg)
	if not QUIET:
		print(f"ERROR [voltage_profile] {msg}",file=error_file,flush=True)
	if type(code) is int:
		exit(code)

output_file = sys.stdout
def debug(msg):
	if DEBUG:
		print(f"DEBUG [voltage_profile] {msg}",file=output_file,flush=True)

def vol_output_print(msg):
	print(f"VOL_OUTPUT [voltage_profile] {msg}",file=output_file,flush=True)
	if VERBOSE:
		verbose(msg)

#
# Inputs handling
#
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
		pass
	elif opt in ("-i", "--input"):
		input_folder = arg.strip()
	elif opt in ("-o", "--output"):
		output_folder = arg.strip()
	elif opt in ("-d", "--data"):
		data_folder = arg.strip()
	elif opt in ("-n", "--network_ID"):
		# only extract the selected network
		network_select = arg.split(" ")
	elif opt in ("-e", "--equipment"):
		pass
	elif opt in ("-g", "--generated"):
		generated_file = arg.strip()
	elif opt in ("-C", "--coodinate"):
		pass
	else:
		error(f"{opt}={arg} is not a valid option", 5);
if input_folder == None:
	error("input_folder must be specified using '-i|--input DIR' option")
if output_folder == None:
	error("output_folder must be specified using '-o|--OUTPUT DIR' option")
if data_folder == None:
	error("data_folder must be specified using '-d|--data DIR' option")
if config_file == None:
	config_file = f"{input_folder}/config.csv"
if not network_select:
	single_file = True

cyme_mdbname = data_folder.split("/")[-1]
if generated_file:
	generated_name = generated_file.split(".")[0]
else:
	generated_name = cyme_mdbname

#
# Load user configuration
#

config = pd.DataFrame({
	"VOL_NETWORK_MATCHES" : [".*"],
	"VOL_OUTPUT" : "/dev/stdout",
	"ERROR_OUTPUT" : "/dev/stderr",
	"WARNING_OUTPUT" : "/dev/stderr",
	"VOLTAGELIMIT" : ["None"],
	"WARNING" : ["True"], 
	"DEBUG" : ["False"],
	"QUIET" : ["False"],
	"VERBOSE" : ["False"],
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
	settings = config
	print(f"Cannot read {config_file}, use default configurations")
for name, values in settings.iterrows():
	if name in config.index:
		config["value"][name] = values[0]
settings = config["value"]

output_file = open(settings["VOL_OUTPUT"],"w")
error_file = open(settings["ERROR_OUTPUT"],"a")
warning_file = open(settings["WARNING_OUTPUT"],"a")

WARNING = True if settings["WARNING"].lower() == "true" else False
DEBUG = True if settings["DEBUG"].lower() == "true" else False
QUIET = True if settings["QUIET"].lower() == "true" else False
VERBOSE = True if settings["VERBOSE"].lower() == "true" else False
LIMIT = None if settings["VOLTAGELIMIT"].lower() == "none" else float(settings["VOLTAGELIMIT"])

print(f"*** Running voltage_profile.py ***")
for name, data in config.iterrows():
	print(f"  {name} = {data['value']}")

#
# -t profile
#
def find(objects,property,value):
	result = []
	for name,values in objects.items():
		if property in values.keys() and values[property] == value:
			result.append(name)
	return result

def get_string(values,prop):
	return values[prop]

def get_complex(values,prop):
	return complex(get_string(values,prop).split(" ")[0].replace('i','j'))

def get_real(values,prop):
	return get_complex(values,prop).real

def get_voltages(values):
	ph = get_string(values,"phases")
	vn = abs(get_complex(values,"nominal_voltage"))
	result = []
	try:
		va = abs(get_complex(values,"voltage_A"))/vn
	except:
		va = None
	try:
		vb = abs(get_complex(values,"voltage_B"))/vn
	except:
		vb = None
	try:
		vc = abs(get_complex(values,"voltage_C"))/vn
	except:
		vc = None
	return ph,vn,va,vb,vc

def profile(objects,root,pos=0):
	fromdata = objects[root]
	ph0,vn0,va0,vb0,vc0 = get_voltages(fromdata)

	count = 0
	for link in find(objects,"from",root):
		linkdata = objects[link]
		linktype = "-"
		if "length" in linkdata.keys():
			linklen = get_real(linkdata,"length")/5280
		else:
			linklen = 0.0
		if not "line" in get_string(linkdata,"class"):
			linktype = "--o"
		if "to" in linkdata.keys():
			to = linkdata["to"]
			todata = objects[to]
			ph1,vn1,va1,vb1,vc1 = get_voltages(todata)
			profile(objects,to,pos+linklen)
			count += 1
			if "A" in ph0 and "A" in ph1: plt.plot([pos,pos+linklen],[va0,va1],"%sk"%linktype)
			if "B" in ph0 and "B" in ph1: plt.plot([pos,pos+linklen],[vb0,vb1],"%sr"%linktype)
			if "C" in ph0 and "C" in ph1: plt.plot([pos,pos+linklen],[vc0,vc1],"%sb"%linktype)
			if LIMIT:
				if (va1 is not None and va1 != 0.0 and va1>1+LIMIT) or (vb1 is not None and vb1 != 0.0 and vb1>1+LIMIT) or (vc1 is not None and vc1 != 0.0 and vc1>1+LIMIT) : 
					warning("cyme-extract voltage_profile.py WARNING: node %s voltage is high (%g, %g, %g), phases = '%s', nominal voltage=%g" % (to,va1*vn1,vb1*vn1,vc1*vn1,ph1,vn1));
				if (va1 is not None and va1 != 0.0 and va1<1-LIMIT) or (vb1 is not None and vb1 != 0.0 and vb1<1-LIMIT) or (vc1 is not None and vc1 != 0.0 and vc1<1-LIMIT) : 
					warning("cyme-extract voltage_profile.py WARNING: node %s voltage is low (%g, %g, %g), phases = '%s', nominal voltage=%g" % (to,va1*vn1,vb1*vn1,vc1*vn1,ph1,vn1));
					print([va1,vb1,vc1,LIMIT])
	if count > 1 and with_nodes:
		plt.plot([pos,pos,pos],[va0,vb0,vc0],':*',color='grey',linewidth=1)
		plt.text(pos,min([va0,vb0,vc0]),"[%s]  "%root,color='grey',size=6,rotation=90,verticalalignment='top',horizontalalignment='center')

with_nodes = False
resolution = "300"
size = "300x200"

if network_select is None:
	network_list = ["ALL"]
else:
	network_list = network_select
network_count = 0
for network_id in network_list:
	network_count += 1
	plt.figure(network_count);
	if network_select is None:
		filename_json = f"{generated_name}.json"
		filename_glm = f"{generated_name}.glm"
		filename_png = f"{generated_name}_voltage_profile.png"
	else:
		filename_json = f"{generated_name}_{network_id}.json"
		filename_glm = f"{generated_name}_{network_id}.glm"
		filename_png = f"{generated_name}_{network_id}_voltage_profile.png"
	try:
		os.system(f"gridlabd {output_folder}/{filename_glm} -o {output_folder}/{filename_json} -w -D minimum_timestep=3600")
	except:
		error(f"Cannot run {output_folder}/{filename_glm}, check GridLAB-D installation or GLM model.", 1)
	with open(f"{output_folder}/{filename_json}","r") as f :
		data = json.load(f)
		assert(data['application']=='gridlabd')
		assert(data['version'] >= '4.2.0')
	
	for obj in find(objects=data["objects"],property="bustype",value="SWING"):
		profile(objects=data["objects"],root=obj)
	plt.xlabel('Distance (miles)')
	plt.ylabel('Voltage (pu)')
	plt.title(data["globals"]["modelname"]["value"])
	plt.grid()
	plt.legend(["A","B","C"])
	plt.tight_layout()
	if LIMIT:
		plt.ylim([1-LIMIT,1+LIMIT])
	plt.savefig(f"{output_folder}/{filename_png}", dpi=int(resolution))


#
# Final checks
#
print(f"CYME-to-GridLAB-D voltage_profile done: {network_count} networks processed, {warning_count} warnings, {error_count} errors.")

