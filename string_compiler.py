import getopt
import sys
import re

from asm import Assembler

flag_ci = False


def printf(fmt, *args):	print(fmt % args)

def c_encode(c):
	if c in '\\\'': return '\\'+c
	return c

def str_encode(s):
	return "".join(reversed([c_encode(x) for x in s]))

def str_xx(s):
	return "".join(reversed(["%02x" % (ord(x)) for x in s]))

def generate_c(d, level, preserve):

	indent = "  " * level

	double = [x for x in d.keys() if len(x) == 2]
	single = [x for x in d.keys() if len(x) == 1]

	count = len(d)
	if "" in d: count = count - 1
	if count>0:
		# if preserve: printf("%s  unsigned c;", indent)
		if double: printf("%s  c = *(unsigned *)(cp+%d);", indent, level*2)
		else: printf("%s  c = *(unsigned char *)(cp+%d);", indent, level*2)

		if flag_ci:
			if double: printf("%s  c |= 0x2020;", indent)
			else: printf("%s  c |= 0x20;", indent)


	for k in double:
		dd = d[k]
		printf("%s  if (c=='%s'){", indent, str_encode(k))
		generate_c(dd, level+1, count>1)
		printf("%s  }", indent)

	if single: printf("%s  c &= 0xff;", indent)
	for k in single:
		dd = d[k]
		printf("%s  if (c=='%s'){", indent, str_encode(k))
		generate_c(dd, level+1, count>1)
		printf("%s  }", indent)



	rv = 0
	if "" in d: rv = d[""]
	printf("%s  return %d", indent, rv)


def generate_asm(asm, d, level):
	global flag_ci

	double = [x for x in d.keys() if len(x) == 2]
	single = [x for x in d.keys() if len(x) == 1]
	short_m = single and not double

	count = len(d)
	if "" in d: count = count - 1

	if count>0:
		if short_m:
			asm.emit("longa off", 0)
			asm.emit("sep #$20", 2)
		if level>0:
			asm.emit("ldy #{}".format(level * 2), 3)
			asm.emit("lda (cp),y", 2)
		else: asm.emit("lda (cp)", 2)

		if flag_ci:
			if short_m: asm.emit("ora #$20", 2)
			else: asm.emit("ora #$2020", 3)

	for k in double:
		dd = d[k]
		l = asm.reserve_label()
		asm.emit("cmp #${}\t; {}".format(str_xx(k), k), 3)
		asm.bne(l)
		generate_asm(asm, dd, level+1)
		asm.emit_label(l)

	if single and double:
		asm.emit("longa off", 0)
		asm.emit("sep #$20", 2)
		short_m = True

	for k in single:
		dd = d[k]
		l = asm.reserve_label()
		asm.emit("cmp #${}\t; {}".format(str_xx(k), k), 2)
		asm.bne(l)
		generate_asm(asm, dd, level+1)
		asm.emit_label(l)

	if short_m:
		asm.emit("longa on", 0)
	if "" in d: 
		asm.emit("ldx #{}".format(d[""]), 3)
	asm.rts()



def process(data, name):
	tree = {}
	for k in data.keys():

		chunks = [k[i*2:i*2+2] for i in range(0,len(k)+1>>1)]

		current = tree
		for x in chunks:
			if x in current:
				current = current[x]
				continue
			tmp = {}
			current[x] = tmp
			current = tmp

		current[""] = data[k]

	# print(tree);
	asm = Assembler(name)
	generate_asm(asm, tree, 0)
	asm.finish(sys.stdout)


def usage(ex=1):
	print("Usage: string_compiler [-i] name [file]")
	sys.exit(ex)


def read_data(f, name):
	global flag_ci

	data = {}
	ln = 0
	for line in f:
		ln = ln + 1
		line = line.strip()
		if line == "" : continue
		if line[0] == "#" : continue

		m = re.match(r'^"([^"]*)"\s+(\d+)$', line)
		if not m:
			err = "{}:{}: Bad data: {}".format(name,ln,line)
			raise Exception(err)
		k = m[1]
		# if flag_ci: k = k.lower()
		if flag_ci:
			k = "".join([chr(ord(x)|0x20) for x in k])

		v = int(m[2])

		if k in data:
			err = "{}:{}: Duplicate string: {}".format(name,ln,k)
			raise Exception(err)

		data[k] = v

	return data

def read_stdin():
	return read_data(sys.stdin, "<stdin>")

def read_file(path):
	with open(path) as f:
		return read_data(f, path)



def main():
	global flag_ci

	argv = sys.argv[1:]
	opts, args = getopt.getopt(argv, "i")
	for k, v in opts:
		if k == "-i": flag_ci = True
		else:
			usage()

	if len(args) < 1 or len(args) > 2:
		usage()

	name = args[0]
	data = {}

	if len(args) == 1 or args[1] == "-":
		data = read_stdin()
	else:
		data = read_file(args[1])

	process(data, name)

	sys.exit(0)
main()