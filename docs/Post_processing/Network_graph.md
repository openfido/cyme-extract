# Network Graph

The network graph postprocessor is invoked add the line `POSTPROC,network_graph.py` in `config.csv`.  Valid additional configuration settings are:

  - `FIGSIZE`:    PNG image dimensions (default "9x6")
  - `NODESIZE`:   size of nodes (default "10")
  - `NODECOLOR`:  color nodes (default "byphase")
  - `FONTSIZE`:   size of label font (default "8")
  - `ROOTNODE`:   root node ID (required for `multipartite` and `shell` graphs)
  - `LAYOUT`:     graph layout (default "nodexy")

Supported layouts:

  - `nodexy`:         use XY coordinates in CYME node table
  - `circular`:       nodes on a circle
  - `kamada_kawai`:   use path length minimization
  - `planar`:         avoid edge intersections
  - `random`:         uniformly in a unit square
  - `shell`:          concentric circles
  - `spring`:         force-directed graph
  - `spectral`:       eigenvector of graph Laplacian
  - `spiral`:         spiral layout
  - `multipartite`:   layers by distance from root node

