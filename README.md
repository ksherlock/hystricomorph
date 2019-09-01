# hystricomorph

A 65816 string compiler

Generates code to match an input string against one or more target strings.

* longest match wins
* generally compared in the order specified
* uses 16-bit comparisons when possible.
* optional case insensitivity

## Usage

    python3 hystricomorph.py [-ilvE] [-o outfile_file] function_name [input_file]

    -i case insensitive comparison
    -E run input file through c pre-processor
    -l return length of matched string in the lsb
    -v be verbose
    -c add implicit 0-terminator to strings

## input file format:

* a leading `#` or `//` indicates a line comment.
* "string" : value
* value may be base 10 or base 16 (`0x` prefix) 16-bit integer.
* string may include standard C character escapes
* no octal.
