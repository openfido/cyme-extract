![CI](https://github.com/openfido/cyme-extract/workflows/CI/badge.svg)

# CYME Model Data Extractor

Extract a CYME MDB file to its constituent tables in CSV format.

## Input

The input folder must contain one or more MDB files, with the extension `.mdb`.

The configuration file `config.csv` may contain any of the following:

### `FILES`

To specify which MDB files are to be extracted, add the following line to `config.csv`:

~~~
FILES,<grep-pattern>
~~~

The default is to extract all MDB files found in the input folder.

### `TABLES`

To specify which tables are to be extracted, add the following line to `config.csv`:

~~~
TABLES,<table-list>
~~~

The default is to extract all tables in the MDB file.

### `EXTRACT`

To specify whether empty tables are to be extracted, add the following line to `config.csv`:

~~~
EXTRACT,[all|non-empty]
~~~

The default is to extract all tables in the MDB file.

### `TIMEZONE`

To specify which timezone to work in, add the following line to `config.csv`:

~~~
TIMEZONE,<country>/<city>
~~~

The default timezone is UTC. If an invalid timezone is used, a complete list of available timezones will be put in the output folder in the file names `timezones.csv`.

## Output

The output folder will contain a folder for each input MDB file, with CSV files corresponding to each of the tables in the input MDB file.  CSV file names correspond to the MDB table name, with the `CYM` prefix removed and using lowercase letters.

An index file named `index.csv` is output containing information about each CSV file created, with the following structure

| database | table | csvname | size | rows |
| -------- | ----- | ------- | ---- | ---- |
| MDBNAME  | TABLENAME | csvname | n-chars | n-rows |

## Docker Usage

You can run this pipeline on a supported docker container (e.g., `ubuntu:20.04`) using the following command:

~~~
host% mkdir input
host% cp my-database.mdb input
host% git clone https://github.com/openfido/cyme-extract --depth 1
host% mkdir output
host% docker run -it -v $PWD:$PWD -e OPENFIDO_INPUT=$PWD/input -e OPENFIDO_OUTPUT=$PWD/output ubuntu:20.04 $PWD/cyme-extract/openfido.sh
~~~
