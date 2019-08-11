import getopt
import sys
import re
from functools import reduce
import subprocess

from asm import Assembler

flag_i = False
flag_l = False
flag_v = False
flag_o = None
flag_E = False


def str_to_int(cc):
	fn = lambda x, y: (x << 8) + ord(y)
	return reduce(fn, reversed(cc), 0)

def str_to_print(cc):
	return "".join([x if (x.isascii() and x.isprintable()) else "." for x in cc])

def or_mask(cc):
	fn = lambda x, y: (x << 8) + (0x20 * (y.isascii() and y.islower()))
	return reduce(fn, reversed(cc), 0)

def mask_char(asm, short_m, old, new):

	if old == new: return new

	if old & ~new: 
		asm.emit("tya", 1)

	if short_m: asm.emit("ora #${:02x}".format(new), 2)
	else: asm.emit("ora #${:04x}".format(new), 3)
	return new


def generate_asm(asm, d, level):
	global flag_i

	double = [x for x in d.keys() if len(x) == 2]
	single = [x for x in d.keys() if len(x) == 1]
	short_m = single and not double

	mask = 0
	tay = False
	if flag_i:
		single.sort(key = or_mask)
		double.sort(key = or_mask)
		if len(single): mask = or_mask(single[0])
		if len(double): mask = or_mask(double[0])

		# need special logic for short-m
		a = set([or_mask(x) for x in double])
		b = set([or_mask(x) for x in single])

		if (0x2000 in a) and (0x0020 in a): tay = True
		if (0x0000 in b) and (0x0020 in a): tay = True
		if (0x0000 in b) and (0x2020 in a): tay = True


	count = len(d)
	if "" in d: count = count - 1

	if count>0:
		if short_m:
			asm.emit("longa off", 0)
			asm.emit("sep #$20", 2)

		if level==0:
			asm.emit("lda (cp)", 2)
		else:
			asm.emit("ldy #{}".format(level * 2), 3)
			asm.emit("lda (cp),y", 2)

		if tay: asm.emit("tay", 1)

		if flag_i: mask = mask_char(asm, short_m, 0, mask)

	for k in double:
		dd = d[k]
		l = asm.reserve_label()
		if flag_i: mask = mask_char(asm, short_m, mask, or_mask(k))
		v = str_to_int(k)
		asm.emit("cmp #${:04x}\t; '{}'".format(v, encode_string(k)), 3)
		asm.bne(l)
		generate_asm(asm, dd, level+1)
		asm.emit_label(l)

	if single and double:
		asm.emit("longa off", 0)
		asm.emit("sep #$20", 2)
		short_m = True
		mask = mask & 0xff

	for k in single:
		dd = d[k]
		l = asm.reserve_label()
		if flag_i: mask = mask_char(asm, short_m, mask, or_mask(k))
		v = str_to_int(k)
		asm.emit("cmp #${:02x}\t; '{}'".format(v, encode_string(k)), 2)
		asm.bne(l)
		generate_asm(asm, dd, level+1)
		asm.emit_label(l)

	if short_m:
		asm.emit("longa on", 0)
	if "" in d: 
		d = d[""]
		asm.emit("ldx #{}\t; '{}'".format(d["__value__"], d["__key__"]), 3)
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

		current[""] = { "__value__": data[k], "__key__": encode_string(k) }

	# print(tree);
	asm = Assembler(name)
	generate_asm(asm, tree, 0)
	asm.finish(sys.stdout)

def decode_string(s):
	global decode_map

	fn = lambda x: decode_map.get(x[1].lower(), '')
	return re.sub(r"\\([xX][A-Fa-f0-9]{2}|.)", fn, s)

def encode_string(s):
	global encode_map
	return "".join([encode_map.get(x, x) for x in s])


def usage(ex=1):
	print("Usage: string_compiler [-i] name [file]")
	sys.exit(ex)


def read_data(f, name):
	global flag_i, flag_l

	data = {}
	ln = 0
	for line in f:
		ln = ln + 1
		line = line.strip()
		if line == "" : continue
		if line[0] == "#" : continue

		m = re.match(r'^"([^"]*)"\s+(\d+|0x[A-Fa-f0-9]+)$', line)
		if not m:
			err = "{}:{}: Bad data: {}".format(name,ln,line)
			raise Exception(err)
		k = orig_k = m[1]
		if flag_i:
			k = k.lower()
		k = decode_string(k)

		tmp = m[2]
		base = 10
		if tmp.startswith("0x"): base = 16
		v = int(tmp, base)
	
		if flag_l:
			if v > 255 or len(orig_k) > 255:
				err = "{}:{} Value too large: {}".format(name, ln, v)
				raise Exception(err)
			v = (v << 8) + len(orig_k) 

		if k in data:
			err = "{}:{}: Duplicate string: {}".format(name,ln,orig_k)
			raise Exception(err)

		data[k] = v

	return data

def read_stdin():
	return read_data(sys.stdin, "<stdin>")

def read_file(path):
	with open(path) as f:
		return read_data(f, path)

def read_cpp(infile):
	args = ["cpp"]
	if infile: args.append(infile)

	x = subprocess.run(args, stdout=subprocess.PIPE, encoding='ascii')
	if x.returncode:
		sys.exit(s.returncode)

	lines = x.stdout.split("\n")
	return read_data(lines, "<cpp-stdin>")


def init_maps():

	global decode_map
	global encode_map

	decode_map = {}
	for i in range(0, 256):
		decode_map["x{:02x}".format(i)] = chr(i)
	decode_map['\\'] = '\\'
	decode_map["'"] = "'"
	decode_map['"'] = '"'
	decode_map['?'] = '?'

	decode_map['a'] = chr(7)
	decode_map['b'] = chr(8)
	decode_map['f'] = chr(12)
	decode_map['n'] = chr(10)
	decode_map['r'] = chr(13)
	decode_map['t'] = chr(9)
	decode_map['v'] = chr(11)

	encode_map = {}
	for i in range(0, 20): encode_map[chr(i)] = "\\x{:02x}".format(i)
	for i in range(127, 256): encode_map[chr(i)] = "\\x{:02x}".format(i)

	encode_map['\\'] = '\\\\'
	encode_map[chr(7)] = '\\a'
	encode_map[chr(8)] = '\\b'
	encode_map[chr(12)] = '\\f'
	encode_map[chr(10)] = '\\n'
	encode_map[chr(13)] = '\\r'
	encode_map[chr(9)] = '\\t'
	encode_map[chr(11)] = '\\v'



def main():
	global flag_i, flag_l

	init_maps()


	argv = sys.argv[1:]
	opts, args = getopt.getopt(argv, "ivo:leE")

	# flags = {}
	# for k, v in opts: flags[k] = v
	# # booleans
	# for k in ("-i","-v","-l","-e"):
	# 	flags[k] = k in flags

	for k, v in opts:
		if k == '-i': flag_i = True
		elif k == '-o': flag_o = v
		elif k == '-v': flag_v = True
		elif k == '-l': flag_l = True
		elif k == '-E': flag_E = True
		else:
			usage()

	if len(args) < 1 or len(args) > 2:
		usage()

	name = args[0]
	data = {}

	if len(args) == 2 and args[1] == "-":
		args.pop()

	if flag_E:
		infile = None
		if len(args) == 2:
			infile = args.pop()
		data = read_cpp(infile)

	elif len(args) == 2:
		data = read_file(args[1])
	else:
		data = read_stdin()

	process(data, name)

	sys.exit(0)

try:
	main()
except Exception as ex:
	print("string16: ", ex, file=sys.stderr, flush=True)
	sys.exit(1)
