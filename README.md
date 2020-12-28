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

