#!/usr/local/python3
"""Draw network graph

Configuration settings (config.csv):

  - PNG_POSTPROC   must be set to "network_graph.py"
  - PNG_FIGNAME    name of figure (default "network_graph.png")
  - PNG_FIGSIZE    PNG image dimensions (default "9x6")
  - PNG_NODESIZE   size of nodes (default "10")
  - PNG_NODECOLOR  color nodes (default "byphase")
  - PNG_FONTSIZE   size of label font (default "8")
  - PNG_ROOTNODE   root node (required for multipartite and shell graphs)
  - PNG_LAYOUT     graph layout (default "nodexy")

Supported layouts:

	nodexy         use XY coordinates in CYME node table
	circular       nodes on a circle
	kamada_kawai   use path length minimization
	planar         avoid edge intersections
	random         uniformly in a unit square
	shell          concentric circles
	spring         force-directed graph
	spectral       eigenvector of graph Laplacian
	spiral         spiral layout
	multipartite   layers by distance from root node
"""

import sys, getopt
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

#
# Required tables to operate properly
#
cyme_tables = ["CYMNETWORK","CYMNODE","CYMSECTION"]

#
# Argument parsing
#
config = {"input":"/","output":"/","from":[],"type":[]}
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
	print("Syntax: python3 -m network_graph.py -i|--input DIR -o|--output DIR -d|--data DIR [-h|--help] [-g|--generated 'file name'][-t|--cyme-tables] [-c|--config CSV] [-e|--equipment 'file name'] [-n|--network_ID 'ID1 ID2 ..']")
	if details:
		print(globals()[__name__].__doc__)
	if type(exit_code) is int:
		exit(exit_code)

def verbose(msg):
		print(f"VERBOSE [network_graph]: {msg}",flush=True)

warning_count = 0
warning_file = sys.stderr
def warning(msg):
	global warning_count
	warning_count += 1
	if WARNING:
		print(f"WARNING [network_graph]: {msg}",file=warning_file,flush=True)
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
		print(f"ERROR [network_graph]: {msg}",file=error_file,flush=True)
	if type(code) is int:
		exit(code)

output_file = sys.stdout
def debug(msg):
	if DEBUG:
		print(f"DEBUG [network_graph]: {msg}",file=output_file,flush=True)

def png_output_print(msg):
	print(f"PNG_OUTPUT [network_graph]: {msg}",file=output_file,flush=True)
	if VERBOSE:
		verbose(msg)

def format_exception(errmsg,ref=None,data=None):
	tb = str(traceback.format_exc().replace('\n','\n  '))
	dd = str(pp.pformat(data).replace('\n','\n  '))
	return "\n  " + tb + "'" + ref  + "' =\n  "+ dd

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

# load the configuration
config = pd.DataFrame({
	"PNG_FIGSIZE" : ["20x10"],
	"PNG_FONTSIZE" : ["1"],
	"PNG_FIGNAME" : ["network_graph.png"],
	"PNG_NODESIZE" : ["0.1"],
	"PNG_NODECOLOR" : ["byphase"],
	"PNG_LAYOUT" : ["nodexy"],
	"PNG_ROOTNODE" : [""],
	"PNG_OUTPUT" : "/dev/stdout",
	"ERROR_OUTPUT" : "/dev/stderr",
	"WARNING_OUTPUT" : "/dev/stderr",
	"WARNING" : ["True"], 
	"DEBUG" : ["False"],
	"QUIET" : ["False"],
	"VERBOSE" : ["False"],
	}).transpose().set_axis(["value"],axis=1,inplace=0)
config.index.name = "name" 
try:
	settings = pd.read_csv(f"{input_folder}/config.csv",
		names=["name","value"],
		comment = "#",
		).set_index("name")
	for name, values in settings.iterrows():
		if name in config.index:
			config["value"][name] = values[0]
except:
	pass
settings = config["value"]
print(f"*** Running network_graph.py ***")
for name, data in config.iterrows():
	print(f"  {name} = {data['value']}")
del config

# load the model
network = pd.read_csv(f"{data_folder}/network.csv",low_memory=False)
nodes = pd.read_csv(f"{data_folder}/node.csv",low_memory=False)
headnodes = pd.read_csv(f"{data_folder}/headnode.csv",low_memory=False)
section = pd.read_csv(f"{data_folder}/section.csv",low_memory=False)
# generate the graph
if network_select is None:
	network_list = ["ALL"]
else:
	network_list = network_select
network_count = 0
for network_id in network_list:
	graph = nx.Graph()
	labels = {}
	network_headnode = []
	network_count += 1
	for index, headnode in headnodes.iterrows():
		if network_id == headnode["NetworkId"]:
			network_headnode.append(headnode["NodeId"])
	if len(network_headnode) > 1:
		error(f"network {network_id} has multiple headnodes", 3)
	for index, node in nodes.iterrows():
		if network_select is None or network_id == node["NetworkId"] or node["NodeId"] in network_headnode:
			labels[node["NodeId"]] = f"{node['NodeId']}\n"
			if settings["PNG_LAYOUT"] == "nodexy":
				# print(f"{node['NodeId']} is ({node['X']},{node['Y']})")
				graph.add_node(node["NodeId"],pos=(node["X"],node["Y"]))
			elif settings["PNG_LAYOUT"] == "multipartite":
				if settings["PNG_ROOTNODE"] == "":
					error("cannot use LAYOUT='multipartite' layout without specifying value for ROOTNODE", 5)
				graph.add_node(node["NodeId"])
			else:
				graph.add_node(node["NodeId"])

	color = ["white","#cc0000","#00cc00","#0000cc","#aaaa00","#aa00aa","#00aaaa","#999999"]
	weight = [0,1,1,1,2,2,2,3]
	for index, edge in section.iterrows():
		if network_select is None or network_id == edge["NetworkId"]:
			phase = edge["Phase"]
			fnode = edge["FromNodeId"]
			tnode = edge["ToNodeId"]
			graph.add_edge(str(fnode),str(tnode),color=color[phase],weight=weight[phase],phase=phase)

	# handle multipartite graph
	if settings["PNG_LAYOUT"] == "multipartite":
		dist = {}
		for node in graph.nodes:
			dist[node] = {"subset": nx.shortest_path_length(graph,node,settings["PNG_ROOTNODE"])}
		nx.set_node_attributes(graph,dist)
		layout_options = {"align":"horizontal","scale":-1.0}
	if settings["PNG_LAYOUT"] == "shell":
		shells = {}
		for node in graph.nodes:
			dist = nx.shortest_path_length(graph,node,settings["PNG_ROOTNODE"])
			if not dist in shells.keys():
				shells[dist] = []
			shells[dist].append(node)
		items = []
		for item in sorted(shells.keys()):
			items.append(shells[item])
		layout_options = {"nlist":items}
	else:
		layout_options = {}

	# output to PNG
	size = settings["PNG_FIGSIZE"].split("x")
	plt.figure(figsize = (int(size[0]),int(size[1])))
	if settings["PNG_LAYOUT"] == "nodexy":
		pos = nx.get_node_attributes(graph,"pos")
		# check node positions
		for node in list(graph.nodes()):
			if node not in pos.keys():
				warning(f"cannot find position data for node '{node}'")
				if len(graph.edges(node)) > 0:
					print()
					for remove_edge in list(graph.edges(node)):
						graph.remove_edge(*remove_edge)
				graph.remove_node(node)
				if node in labels.keys():
					del labels[node]
	elif hasattr(nx,settings["PNG_LAYOUT"]+"_layout"):
		call = getattr(nx,settings["PNG_LAYOUT"]+"_layout")
		pos = call(graph,**layout_options)
	else:
		error("LAYOUT={settings['LAYOUT']} is invalid", 10)
	
	edges = graph.edges()
	colors = [graph[u][v]["color"] for u,v in edges]
	weights = [graph[u][v]["weight"] for u,v in edges]
	if not settings["PNG_NODECOLOR"] or settings["PNG_NODECOLOR"] == "byphase":
		node_colors = {}
		for node in graph.nodes:
			phase = 0
			for edge in graph.edges(node):
				phase |= graph.edges[edge]["phase"]
			node_colors[node] = {"color":color[phase]}
		nx.set_node_attributes(graph,node_colors)
		node_colors = nx.get_node_attributes(graph,"color").values()
	else:
		node_colors = settings["PNG_NODECOLOR"]

	try:
		nx.draw(graph, pos,
			with_labels = True,
			edge_color = colors,
			width = weights,
			labels = labels,
			node_size = int(settings["PNG_NODESIZE"]),
			node_color = node_colors,
			font_size = int(settings["PNG_FONTSIZE"]),
			)
		if network_select:
			plt.savefig(f"{output_folder}/{network_id}_{settings['PNG_FIGNAME']}")
		else:
			plt.savefig(f"{output_folder}/{settings['PNG_FIGNAME']}")
	except nx.NetworkXError as err:
		warning(f"Cannot generate the network plot because {err}")

#
# Final checks
#
print(f"CYME-to-GridLAB-D network_graph done: {network_count} networks processed, {warning_count} warnings, {error_count} errors.")
