#!/usr/bin/python3
import sys, os, time
import json 
import getopt
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import math
import numpy as np

opts, args = getopt.getopt(sys.argv[1:],"hc:i:o:d:tn:e:",["help","config=","input=","output=","data=","cyme-tables","network_ID=","equipment_file="])
def help(exit_code=None,details=False):
	print("Syntax: python3 -m voltage_profile.py -i|--input DIR -o|--output DIR -d|--data DIR [-h|--help] [-t|--cyme-tables] [-c|--config CSV] [-e|--equipment file_name] [-n|--network_ID 'ID1 ID2 ..']")
	if details:
		print(globals()[__name__].__doc__)
	if type(exit_code) is int:
		exit(exit_code)

if not opts : 
	help(1)

input_folder = None
output_folder = None
data_folder = None
config_file = None
equipment_file = None
network_select = None
single_file = False
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
	elif opt in ("-n", "--network_ID"):
		# only extract the selected network
		network_select = arg.split(" ")
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
if not network_select:
	single_file = True

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
			if limit:
				if (not va1 is None and va1>1+limit) or (not vb1 is None and vb1>1+limit) or (not vc1 is None and vc1>1+limit) : 
					print("cyme-extract voltage_profile.py WARNING: node %s voltage is high (%g, %g, %g), phases = '%s', nominal voltage=%g" % (to,va1*vn1,vb1*vn1,vc1*vn1,ph1,vn1));
				if (not va1 is None and va1<1-limit) or (not vb1 is None and vb1<1-limit) or (not vc1 is None and vc1<1-limit) : 
					print("cyme-extract voltage_profile.py WARNING: node %s voltage is low (%g, %g, %g), phases = '%s', nominal voltage=%g" % (to,va1*vn1,vb1*vn1,vc1*vn1,ph1,vn1));
	if count > 1 and with_nodes:
		plt.plot([pos,pos,pos],[va0,vb0,vc0],':*',color='grey',linewidth=1)
		plt.text(pos,min([va0,vb0,vc0]),"[%s]  "%root,color='grey',size=6,rotation=90,verticalalignment='top',horizontalalignment='center')

with_nodes = False
resolution = "300"
size = "300x200"
limit = 1.1
cyme_mdbname = data_folder.split("/")[-1]
if network_select is None:
	network_list = ["ALL"]
else:
	network_list = network_select
figure_id = 0
for network_id in network_list:
	figure_id += 1
	plt.figure(figure_id);
	if network_select is None:
		filename_json = f"{cyme_mdbname}.json"
		filename_glm = f"{cyme_mdbname}.glm"
		filename_png = f"{cyme_mdbname}.png"
	else:
		filename_json = f"{cyme_mdbname}_{network_id}.json"
		filename_glm = f"{cyme_mdbname}_{network_id}.glm"
		filename_png = f"{cyme_mdbname}_{network_id}.png"
	try:
		os.system(f"gridlabd {output_folder}/{filename_glm} -o {output_folder}/{filename_json}")
	except:
		raise Exception(f"Cannot run {output_folder}/{filename_glm}, check GridLAB-D installation or GLM model.")
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
	#plt.legend(["A","B","C"])
	#plt.tight_layout()
	if limit:
		plt.ylim([1-limit,1+limit])
	plt.savefig(f"{output_folder}/{filename_png}", dpi=int(resolution))


# 	plt.xlabel('Distance (miles)')
# 	plt.ylabel('Voltage (pu)')
# 	plt.title(data["globals"]["modelname"]["value"])
# 	plt.grid()
# 	#plt.legend(["A","B","C"])
# 	#plt.tight_layout()
# 	if limit:
# 		plt.ylim([1-limit,1+limit])
# 	plt.savefig(filename_png, dpi=int(resolution))

