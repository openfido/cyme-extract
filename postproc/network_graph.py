#!/usr/bin/python3
"""Draw network graph

Configuration settings (config.csv):

  - PNG_POSTPROC   must be set to "network_graph.py"
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

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

# load the configuration
config = pd.DataFrame({
	"PNG_FIGSIZE" : ["9x6"],
	"PNG_FONTSIZE" : ["8"],
	"PNG_NODESIZE" : ["10"],
	"PNG_NODECOLOR" : ["byphase"],
	"PNG_LAYOUT" : ["nodexy"],
	"PNG_ROOTNODE" : [""],
	}).transpose().set_axis(["value"],axis=1,inplace=0)
config.index.name = "name" 
try:
	settings = pd.read_csv("../config.csv",
		names=["name","value"],
		comment = "#",
		).set_index("name")
	for name, values in settings.iterrows():
		if name in config.index:
			config["value"][name] = values[0]
except:
	pass
settings = config["value"]
print(f"Running network_graph.py:")
for name, data in config.iterrows():
	print(f"  {name} = {data['value']}")
del config

# load the model
network = pd.read_csv("network.csv")
nodes = pd.read_csv("node.csv")
section = pd.read_csv("section.csv")

# generate the graph
graph = nx.Graph()
labels = {}
for index, node in nodes.iterrows():
	labels[node["NodeId"]] = f"{node['NodeId']}\n"
	if settings["PNG_LAYOUT"] == "nodexy":
		graph.add_node(node["NodeId"],pos=(node["X"],node["Y"]))
	elif settings["PNG_LAYOUT"] == "multipartite":
		if settings["PNG_ROOTNODE"] == "":
			raise Exception("cannot use LAYOUT='multipartite' layout without specifying value for ROOTNODE")
		graph.add_node(node["NodeId"])
	else:
		graph.add_node(node["NodeId"])

color = ["white","#cc0000","#00cc00","#0000cc","#aaaa00","#aa00aa","#00aaaa","#999999"]
weight = [0,1,1,2,1,2,2,3]
for index, edge in section.iterrows():
	phase = edge["Phase"]
	fnode = edge["FromNodeId"]
	tnode = edge["ToNodeId"]
	graph.add_edge(fnode,tnode,color=color[phase],weight=weight[phase],phase=phase)
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
	print(items)
	layout_options = {"nlist":items}
else:
	layout_options = {}

# output to PNG
size = settings["PNG_FIGSIZE"].split("x")
plt.figure(figsize = (int(size[0]),int(size[1])))
edges = graph.edges()
colors = [graph[u][v]["color"] for u,v in edges]
weights = [graph[u][v]["weight"] for u,v in edges]
if settings["PNG_LAYOUT"] == "nodexy":
	pos = nx.get_node_attributes(graph,"pos")
elif hasattr(nx,settings["PNG_LAYOUT"]+"_layout"):
	call = getattr(nx,settings["PNG_LAYOUT"]+"_layout")
	pos = call(graph,**layout_options)
else:
	raise Exception("LAYOUT={settings['LAYOUT']} is invalid")
nx.draw(graph, pos,
	with_labels = True,
	edge_color = colors,
	width = weights,
	labels = labels,
	node_size = int(settings["PNG_NODESIZE"]),
	node_color = node_colors,
	font_size = int(settings["PNG_FONTSIZE"]),
	)
plt.savefig("../network_graph.png")
