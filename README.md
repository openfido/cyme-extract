Pipeline status: [![validation](https://github.com/openfido/cyme-extract/actions/workflows/main.yml/badge.svg)](https://github.com/openfido/cyme-extract/actions/workflows/main.yml)

# CYME Model Data Extractor

Extract a CYME MDB file to its constituent tables in CSV format.

## Input

The input folder must contain one or more MDB files, with the extension `.mdb`.

File `config.csv`:

| Parameter name | Default value   | Remarks                                                                                                                             |
| :------------- | :-------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| `FILES`        | `*.mdb`         | Supports patterns. Single filename example: `my-network.mdb`                                                                        |
| `TABLES`       | `*`             | Supports patterns. Most CYME tables match `CYM*`                                                                                    |
| `EXTRACT`      | `non-empty`     | Allowed values are `all` or `non-empty`                                                                                             |
| `TIMEZONE`     | `US/CA`         | General format is `<country>/city`                                                                                                  |
| `POSTPROC`     | `network_graph` | Allowed post-processors are list in `postproc` folder. Current valid values are `network_graph`, `voltage_profile`, and `write_glm` |
| `OUTPUT`       | `zip csv json`  | File extensions to copy to the output folder.                                                                                       |

## Examples

Example 1 is based on the [autotest/input_1](https://github.com/openfido/cyme-extract/tree/main/autotest/input_1).

[config.csv](file:autotest/input_1/config.csv)

[config.glm](file:autotest/input_1/config.glm)

[modify.csv](file:autotest/input_1/modify.csv)

[settings.csv](file:autotest/input_1/settings.csv)

## Output

The output folder will contain a folder for each input MDB file, with CSV files corresponding to each of the tables in the input MDB file. CSV file names correspond to the MDB table name, with the `CYM` prefix removed and using lowercase letters.

An index file named `index.csv` is output containing information about each CSV file created, with the following structure

| database  | table          | csvname     | size      | rows     |
| --------- | -------------- | ----------- | --------- | -------- |
| _mdbname_ | _CYMTABLENAME_ | _tablename_ | _n-chars_ | _n-rows_ |

## Docker Usage

You can run this pipeline on a supported docker container (e.g., `ubuntu:20.04`) using the following command:

```
host% mkdir input
host% cp my-database.mdb input
host% git clone https://github.com/openfido/cyme-extract --depth 1
host% mkdir output
host% docker run -it -v $PWD:$PWD -e OPENFIDO_INPUT=$PWD/input -e OPENFIDO_OUTPUT=$PWD/output ubuntu:20.04 $PWD/cyme-extract/openfido.sh
```

## CLI Usage

The following command will allow you to run the cyme-extract pipeline using the openfido CLI. The syntax is as follows:

    $ openfido run cyme-extract FILENAME.mdb GLM_FILENAME.glm '-i|--input INPUTDIR -o|--output OUTPUTDIR -d|--data DATADIR [-c|--config [CONFIGCSV]] [-h|--help] [-t|--cyme-tables] [-s|--single] [-n|--network ID "ID1 ID2 ..."] [-e|--equipment EQUIPMENTCSV] [-g|--generated FILENAME] [-C|--coordinate CSV]'

Input folder should contain a `config.csv` along with the MDB file(s) to convert. Using the postproc usecases directly needs a folder that contains all required CSV tables. The CSV should be converted from the MDB using `MTBTool` or `pandas_access` or another package.

### Examples

#### Openfido CLI

Shell:

```
$ openfido run cyme-extract IEEE123.mdb IEEE123.glm
```

```
$ openfido run cyme-extract IEEE123.mdb IEEE123.glm '-i ./input -o ./output -C geodata.csv'
```

```
$ openfido run cyme-extract IEEE123.mdb IEEE123.glm '-n ID1 -e Equipment.mdb'
```

```
$ openfido run cyme-extract IEEE123.mdb IEEE123.glm '-n "ID1 ID2 ID3" -e Equipment.mdb'
```

#### Python

Shell:

```
$ python3 write_glm.py -i ./ -o ./ -d ./IEEE13_tables -c ./config.csv -g IEEE13.glm -C geodata.csv
```

```
$ python3 network_graph.py -i ./ -o ./ -d ./IEEE13_tables -c ./config.csv -g IEEE13.glm
```

```
$ python3 voltage_profile.py -i ./ -o ./ -d ./IEEE13_tables -c ./config.csv -g IEEE13.glm
```
