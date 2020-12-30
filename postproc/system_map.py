#!/usr/bin/python3

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

# load the configuration
config = pd.DataFrame({
	"FIGSIZE" : ["12x12"],
	"FONTSIZE" : ["8"],
	"NODESIZE" : ["20"],
	"SCALE" : ["0.01"]
	}).transpose().set_axis(["value"],axis=1,inplace=0)
config.index.name = "name" 
try:
	settings = pd.read_csv("autotest/output_2/config.csv",names=["name","value"]).set_index("name")
	for name, values in settings.iterrows():
		if name in result.index:
			config["value"][name] = values
except:
	pass
settings = config["value"]

# load the model
nodes = pd.read_csv("node.csv")
section = pd.read_csv("section.csv")

nodes.to_csv("../node.csv",index=False)
section.to_csv("../section.csv",index=False)

# generate the graph
graph = nx.Graph()
scale = float(settings["SCALE"])
for index, node in nodes.iterrows():
	graph.add_node(node["NodeId"],pos=(node["X"]*scale,node["Y"]*scale))

color = ["white","red","green","yellow","blue","cyan","magenta","black"]
weight = [0,1,1,2,1,2,2,3]
for index, edge in section.iterrows():
	phase = edge["Phase"]
	fnode = edge["FromNodeId"]
	tnode = edge["ToNodeId"]
	graph.add_edge(fnode,tnode,color=color[phase],weight=weight[phase])

# output to PNG
edges = graph.edges()
colors = [graph[u][v]["color"] for u,v in edges]
weights = [graph[u][v]["weight"] for u,v in edges]
pos = nx.get_node_attributes(graph,"pos")
nx.draw(graph, pos,
	with_labels = True,
	edge_color = colors,
	width = weights,
	node_size = int(settings["NODESIZE"]),
	font_size = int(settings["FONTSIZE"]),
	)

plt.savefig("../system_map.png",
	figsize = settings["FIGSIZE"].split("x"),
	)
