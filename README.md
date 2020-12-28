# CYME Model Data Extractor

Extract a CYME MDB file to its constituent tables in CSV format.

## Input

The input folder must contain one or more MDB files, with the extension `.mdb`.

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
