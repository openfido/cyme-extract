# Write GLM

The `write_glm` postprocessor can be used by adding the line `POSTPROC,write_glm.py` to the `config.csv` file.

Settings in the `config.csv` file that affect the `write_glm` processor include:

  - `GLM_NETWORK_PREFIX` : file name prefix to use for the output GLM file (default is `network_`)
  - `GLM_NETWORK_MATCHES` : network name pattern to select networks to output (default is all)
  - `GLM_NOMINAL_VOLTAGE` : nominal voltage to use when generating node and link objects (default is none)
  - `GLM_INCLUDE` : GLM file to include (default is none)
  - `GLM_DEFINE` : GLM define flag, may be used only once (default is none)
  - `GLM_ERRORS` : disposition of error messages (options are "stdout", "stderr", or the default "exception")
  - `GLM_WARNINGS` : disposition of warning messages (options are "stderr", "exception" or the default "stdout")
  - `GLM_MODIFY` : name of model modification records to load after creating model

The general structure of the output GLM is as follows:

1. `#define` statement providing information about the context in which the GLM model was created.
2. `#define` statement from the `GLM_DEFINE` setting, if any.
3. `#include` statement from the `GLM_INCLUDE` setting, if any.
4. `powerflow` module statement to select the `NR` solver.
5. `object` definitions from the CYME database
6. `modify` statements from the `GLM_MODIFY` setting, if any.

## Globals

The following global variables are set when the model is loaded in GridLAB-D:

### Application information
 - `APP_COMMAND`: full local pathname to program used to create GLM file
 - `APP_VERSION`: version number of the application used to create GLM file

### GIT information
 - `GIT_PROJECT`: github project remote origin
 - `GIT_COMMIT`: github project commit id
 - `GIT_BRANCH`: github branch name

### GLM information
 - `GLM_PATHNAME`: local GLM file name
 - `GLM_CREATED`: date GLM file was created
 - `GLM_USER`: user name when GLM was created
 - `GLM_WORKDIR`: working directory when GLM was created
 - `GLM_LANG`: OS language when GLM was created, if any

### CYME information
 - `CYME_MDBNAME`: CYME MDB name
 - `CYME_VERSION`: CYME MDB version
 - `CYME_CREATED`: date CYME MDB was created
 - `CYME_MODIFIED`: date CYME MDB was last modified
 - `CYME_LOADFACTOR`: CYME network loading factor
 - `CYME_NETWORKID`: CYME network id

## Settings

### `GLM_NOMINAL_VOLTAGE`

The nominal voltage must be specified either in the `config.csv` or in the included GLM file.

### `GLM_NETWORK_PREFIX`

Each network in the CYME database will be output in a separate GLM file using the name of the network with the network prefix.

### `GLM_NETWORK_MATCHES`

The network pattern matching uses POSIX regular expressions to match network names starting with the first character of the network name.  Here are some useful examples:

  - `abc`: match all network names that start with the string "abc"
  - `abc$`: match the network name "abc" only
  - `.*`: match all network names
  - `.*abc`: match all networks containing the string "abc"
  - `.*abc$`: match all networks ending with the string "abc"
  - `[0-9]`: match all networks starting with the digits 0 through 9
  - `.*[0-9]`: match all networks containing the digits 0 through 9
  - `.*[0-9]$`: match all networks ending with the digits 0 through 9

For details on POSIX pattern matching see [POSIX Regular Expression Documentation](https://en.wikibooks.org/wiki/Regular_Expressions/POSIX_Basic_Regular_Expressions).

### `GLM_INCLUDE` 

A single `#include` macro may be added after the `#define` specified by `GLM_DEFINE`.  This allows the define statement to control the behavior of the include file.

### `GLM_DEFINE`

A single `#define` may be specified to alter the behavior of the include file, object definitions, and modify statements.

### `GLM_ERRORS`

By default processing errors result in a exception that causes the post-processor to fail.  Errors can be set to write a message to either `stdout` or `stderr` without causing an exception.

### `GLM_WARNINGS`

By default processing warnings result in output to `stdout`.  Warning can be set to write to `stderr` or cause raise exception that causes the post-processor to fail.

### `GLM_MODIFY`

A single CSV file may be processed after the GLM objects are created to enable modification of object properties, if desired.  The format of the modification file is as follows:

~~~
<object1>,<property1>,<value1>
<object2>,<property2>,<value2>
...
<objectN>,<propertyN>,<valueN>
~~~

## CYME Devices

The following CYME device types can be converted to GridLAB-D classes:

| CYME Device | CYME Device Type | GridLAB-D Class |
| :---------: | :--------------: | :-------------: |
| `UndergroundLine` | 1 | `underground_line` |
| `OverheadLine` | 2 | `overhead_line` |
| `OverheadByPhase` | 3 | `overhead_line` |
| `Regulator` |  4 | `regulator` |
| `Transformer` |  5 | `transformer` |
| `Breaker` |  8 | `breaker` |
| `Recloser` |  10 | `recloser` |
| `Sectionalizer` |  12 | `sectionalizer` |
| `Switch` |  13 | `switch` |
| `Fuse` |  14 | `fuse` |
| `ShuntCapacitor` |  17 | `capacitor` |
| `SpotLoad` |  20 | `load` |
| `OverheadLineUnbalanced` |  23 | `overhead_line` |

## Object Naming Convention

CYME record ids are converted to GridLAB-D object names using a name prefix based on the GridLAB-D object class, as follows:

| Class | Prefix |
| :---: | :----: |
| `billdump` | `BD_` |
| `capacitor` | `CA_` |
| `currdump` | `CD_` |
| `emissions` | `EM_` |
| `fault_check` | `FC_` |
| `frequency_gen` | `FG_` |
| `fuse` | `FS_` |
| `impedance_dump` | `ID_` |
| `line` | `LN_` |
| `line_configuration` | `LC_` |
| `line_sensor` | `LS_` |
| `line_spacing` | `LG_` |
| `link` | `LK_` |
| `load` | `LD_` |
| `load_tracker` | `LT_` |
| `meter` | `ME_` |
| `motor` | `MO_` |
| `node` | `ND_` |
| `overhead_line` | `OL` |
| `overhead_line_conductor` | `OC_` |
| `pole` | `PO_` |
| `pole_configuration` | `PC_` |
| `power_metrics` | `PM_` |
| `powerflow_library` | `PL_` |
| `powerflow_object` | `PO_` |
| `pqload` | `PQ_` |
| `recloser` | `RE_` |
| `regulator` | `RG_` |
| `regulator_configuration` | `RC_` |
| `restoration` | `RS_` |
| `sectionalizer` | `SE_` |
| `series_reactor` | `SR_` |
| `substation` | `SS_` |
| `switch` | `SW_` |
| `switch_coordinator` | `SC_` |
| `transformer` | `TF_` |
| `transformer_configuration` | `TC_` |
| `triplex_line` | `XL_` |
| `triplex_line_conductor` | `XC_` |
| `triplex_line_configuration` | `XG_` |
| `triplex_load` | `XD_` |
| `triplex_meter` | `XM_` |
| `triplex_node` | `XN_` |
| `underground_line` | `UL_` |
| `underground_line_conductor` | `UC_` |
| `vfd` | `VF_` |
| `volt_var_control` | `VV_` |
| `voltdump` | `VD_` |

If a class is not found, the prefix `Z<num>_` is used where `<num>` is a number based on the size of the class in the class name dictionary at the time the new prefix was create.

## Example

The following example converts the `IEEE13.mdb` file to GridLAB-D `glm` format:

The file `config.csv` specifies the non-empty tables to extract and convert to GLM, the nominal voltage to use, and the modification file to use.

~~~
TABLES,CYMNETWORK CYMHEADNODE CYMNODE CYMSECTION CYMSECTIONDEVICE CYMOVERHEADBYPHASE CYMOVERHEADLINEUNBALANCED CYMEQCONDUCTOR CYMEQGEOMETRICALARRANGEMENT CYMEQOVERHEADLINEUNBALANCED CYMSWITCH CYMCUSTOMERLOAD CYMSHUNTCAPACITOR CYMTRANSFORMER CYMEQTRANSFORMER CYMREGULATOR
EXTRACT,non-empty
POSTPROC,write_glm.py
GLM_NOMINAL_VOLTAGE,2.40178 kV
GLM_MODIFY,modify.csv
~~~

The file `modify.csv` specifies that the shunt capacitor `L675CAP` on phase A switch is to be removed.

~~~
CA_L675CAP,switchA,OPEN
~~~
