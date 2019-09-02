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

## output file

```
python3 hystricomorph.py -c -i -l match
"ABC" : 1
"ABCD" : 2
```

This will generate a function (`int match(const char *)`) which is essentially:

```
int match(const char *cp) {
	if (!strcasecmp(cp, "abcd")) return (2 << 8) | 4;
	if (!strcasecmp(cp, "abc")) return (1 << 8) | 3;
	return 0;
}
```

(without the `-c` flag it would be more akin to `memcmp` than `strcmp`.
Actual matching logic is based on the character count not a terminal character
so embedded `0`s match correctly.)

But hopefully more efficient...

```
* generated Sun Sep  1 22:34:34 2019

	case on

dummy	START
	END

match	START

cp	equ 5

	phb
	tsc
	phd
	tcd
	pei cp+1
	plb
	plb
	jsr _action
	rep #$20
	lda 1
	sta 5
	lda 3
	sta 7
	pld
	pla
	pla
	txa
	plb
	rtl

_action	anop
	ldx #0

	longi on
	longa on
	lda (cp)
	ora #$2020
	cmp #$6261	; 'ab'
	bne _4
	ldy #2
	lda (cp),y
	ora #$0020
	cmp #$0063	; 'c\x00'
	bne _2
	ldx #259	; 'abc\x00'
	rts
_2	anop
	ora #$2020
	cmp #$6463	; 'cd'
	bne _4
	longa off
	sep #$20
	ldy #4
	lda (cp),y
	cmp #$00	; '\x00'
	bne _4
	ldx #516	; 'abcd\x00'
_4	anop
	rts
	END
```
