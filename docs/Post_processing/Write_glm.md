# Write GLM

The `write_glm` postprocessor can be used by adding the line `POSTPROC,write_glm.py` to the `config.csv` file.

Settings in the `config.csv` file that affect the `write_glm` processor include:

  - `GLM_NETWORK_PREFIX` : specify the file name prefix to use for the output GLM file (default is `network_`)
  - `GLM_NETWORK_MATCHES` : specify the network name pattern to select networks to output (default is all)
  - `GLM_NOMINAL_VOLTAGE` : specify the nominal voltage to use when generating node and link objects (default is none)
  - `GLM_INCLUDE` : specify the GLM file to include (default is none)
  - `GLM_DEFINE` : specify a GLM define flag (default is none)
  - `GLM_DISTRIBUTED_LOAD_POSITION` : specify the position for a distributed load equivalent (default is 2/3 down the line)
  - GLM_ERRORS" : specify the disposition of error messages (options are "stdout", "stderr", or the default "exception")
  - GLM_WARNINGS" : specify the disposition of warning messages (options are "stderr", "exception" or the default "stdout")

Note that the nominal voltage must be specified either in the `config.csv` or in the included GLM file.

Each network in the CYME database will be output in a separate GLM file using the name of the network with the network prefix.

The network pattern matching uses POSIX regular expressions to match network names starting with the first character of the network name.  Here are some useful examples:

  - `abc`: match all network names that start with the string "abc"
  - `abc$`: match the network name "abc" only
  - `.*`: match all network names
  - `.*abc`: match all networks containing the string "abc"
  - `.*abc$`: match all networks ending with the string "abc"
  - `[0-9]`: match all networks starting with the digits 0 through 9
  - `.*[0-9]`: match all networks containing the digits 0 through 9
  - `.*[0-9]$`: match all networks ending with the digits 0 through 9

For details on POSIX pattern matching see [[https://en.wikibooks.org/wiki/Regular_Expressions/POSIX_Basic_Regular_Expressions]].
