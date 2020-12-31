# Network Graph

The network graph postprocessor is invoked add the line `POSTPROC,network_graph.py` in `config.csv`.  Valid additional configuration settings are:

  - `PNG_FIGSIZE`:    PNG image dimensions (default "9x6")
  - `PNG_NODESIZE`:   size of nodes (default "10")
  - `PNG_NODECOLOR`:  color nodes (default "byphase")
  - `PNG_FONTSIZE`:   size of label font (default "8")
  - `PNG_ROOTNODE`:   root node ID (required for `multipartite` and `shell` graphs)
  - `PNG_LAYOUT`:     graph layout (default "nodexy")

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

