# Network Graph

The network graph postprocessor is invoked using the `POSTPROC,network_graph.py` setting in `config.csv`.  Valid additional configuration settings are:

  - POSTPROC   must be set to "network_graph.py"
  - FIGSIZE    PNG image dimensions (default "9x6")
  - NODESIZE   size of nodes (default "10")
  - NODECOLOR  color nodes (default "byphase")
  - FONTSIZE   size of label font (default "8")
  - ROOTNODE   root node (required for multipartite and shell graphs)
  - LAYOUT     graph layout (default "nodexy")

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

