#!/usr/bin/python3

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

# load the configuration
config = pd.DataFrame({
	"FIGSIZE" : ["12x12"],
	"FONTSIZE" : ["8"],
	"NODESIZE" : ["20"],
	}).transpose().set_axis(["value"],axis=1,inplace=0)
config.index.name = "name" 
try:
	settings = pd.read_csv("autotest/output_2/config.csv",names=["name","value"]).set_index("name")
	for name, values in settings.iterrows():
		if name in result.index:
			config["value"][name] = values
except:
	pass


# load the model
nodes = pd.read_csv("node.csv")
section = pd.read_csv("section.csv")

nodes.to_csv("../node.csv",index=False)
section.to_csv("../section.csv",index=False)

# generate the graph
graph = nx.Graph()

for index, node in nodes.iterrows():
	graph.add_node(node["NodeId"])

color = ["white","red","green","yellow","blue","cyan","magenta","black"]
weight = [0,1,1,2,1,2,2,3]
for index, edge in section.iterrows():
	phase = edge["Phase"]
	fnode = edge["FromNodeId"]
	tnode = edge["ToNodeId"]
	graph.add_edge(fnode,tnode,color=color[phase],weight=weight[phase])

# output to PNG
edges = graph.edges()
colors = [graph[u][v]['color'] for u,v in edges]
weights = [graph[u][v]['weight'] for u,v in edges]
nx.draw(graph, 
	with_labels = True,
	edge_color = colors,
	width = weights,
	node_size = int(config["value"]["NODESIZE"]),
	font_size = int(config["value"]["FONTSIZE"]),
	)

plt.savefig("../system_map.png",
	figsize = config["value"]["FIGSIZE"].split("x"),
	)
