#!/usr/bin/python3

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

# load the configuration
config = pd.DataFrame({
	"FIGSIZE" : ["9x6"],
	"FONTSIZE" : ["8"],
	"NODESIZE" : ["20"],
	"LAYOUT" : ["nodexy"],
	}).transpose().set_axis(["value"],axis=1,inplace=0)
config.index.name = "name" 
try:
	settings = pd.read_csv("../config.csv",names=["name","value"]).set_index("name")
	for name, values in settings.iterrows():
		if name in config.index:
			config["value"][name] = values[0]
except:
	pass
settings = config["value"]

# load the model
nodes = pd.read_csv("node.csv")
section = pd.read_csv("section.csv")

# generate the graph
graph = nx.Graph()
labels = {}
for index, node in nodes.iterrows():
	labels[node["NodeId"]] = f"{' '*3*len(node['NodeId'])}{node['NodeId']}\n\n"
	if settings["LAYOUT"] == "nodexy":
		graph.add_node(node["NodeId"],pos=(node["X"],node["Y"]))
	else:
		graph.add_node(node["NodeId"])

color = ["white","red","green","yellow","blue","cyan","magenta","black"]
weight = [0,1,1,2,1,2,2,3]
for index, edge in section.iterrows():
	phase = edge["Phase"]
	fnode = edge["FromNodeId"]
	tnode = edge["ToNodeId"]
	graph.add_edge(fnode,tnode,color=color[phase],weight=weight[phase])

# output to PNG
size = settings["FIGSIZE"].split("x")
plt.figure(figsize = (int(size[0]),int(size[1])))
edges = graph.edges()
colors = [graph[u][v]["color"] for u,v in edges]
weights = [graph[u][v]["weight"] for u,v in edges]
if settings["LAYOUT"] == "nodexy":
	pos = nx.get_node_attributes(graph,"pos")
elif settings["LAYOUT"] == "spring":
	pos = nx.spring_layout(graph)
else:
	raise Exception("LAYOUT={settings['LAYOUT']} is invalid")
nx.draw(graph, pos,
	with_labels = True,
	edge_color = colors,
	width = weights,
	labels = labels,
	node_size = int(settings["NODESIZE"]),
	font_size = int(settings["FONTSIZE"]),
	)
plt.savefig("../system_map.png")
