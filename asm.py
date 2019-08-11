from textwrap import indent, dedent
from time import asctime

class Block(object):
	def __init__(self):
		self.size = 0
		self.branch_target = None
		self.branch_long = False
		self.branch_type = None
		self.branch_size = 0
		self.labels = []
		self.instr = []
		self.rts = False
		self.mx = 0b11

	def empty(self):
		return self.size + self.branch_size == 0



class Assembler(object):

	__inverted_branch = {
		'bne': 'beq',
		'beq': 'bne',
		'bvc': 'bvs',
		'bvs': 'bvc',
		'bpl': 'bmi',
		'bmi': 'bpl',
		'bcc': 'bcs',
		'bcs': 'bcc'
	}

	def __init__(self, name):
		self.name = name
		self.mx = 0b11
		self.blocks = []
		self.b = None
		self.label = 0

		self.new_block()


	def reserve_label(self):
		self.label = self.label + 1
		return "_%d" % (self.label)

	def emit_label(self, l):
		if not self.b.empty():
			self.new_block()
		self.b.labels.append(l)

	def rts(self):
		if not self.b.empty():
			self.new_block()
		self.emit("rts",1)
		self.b.rts = True
		self.new_block()

	def new_block(self):
		self.b = Block()
		self.b.mx = self.mx

		self.blocks.append(self.b)

	def bne(self, l):
		self.b.branch_type = 'bne'
		self.b.branch_target = l
		self.b.branch_size = 2
		self.new_block()

	def emit(self, op, size):
		self.b.size = self.b.size + size
		self.b.instr.append("\t" + op)

	def mx_common(self, onoff, mask):

		mx = self.mx

		if onoff: mx |= mask
		else: mx &= ~mask

		if mx == self.mx: return

		if not self.b.empty():
			self.new_block()

		self.b.mx = mx
		self.mx = mx

	@property
	def longm(self):
		return bool(self.mx & 0b10)

	@longm.setter
	def longm(self, value):
		self.mx_common(value, 0b10)

	@property
	def longx(self):
		return bool(self.mx & 0b01)

	@longx.setter
	def longx(self, value):
		self.mx_common(value, 0b01)

	def merge_rts(self):
		blocks = []
		prev = None
		for b in self.blocks:
			if b.rts and prev and prev.rts:
				prev.labels.extend(b.labels)
				continue
			blocks.append(b)
			prev = b

		self.blocks = blocks

	def merge_labels(self):

		map = {}

		for b in self.blocks:
			ll = b.labels
			if len(ll)>0:
				first = ll[0]
				for l in ll: map[l] = first
				b.labels = [first]

		for b in self.blocks:
			if b.branch_target:
				b.branch_target = map[b.branch_target]

	def reify_branches(self):
		# in practice all branches are forward
		# could be clever and try to find a backwards rts branch island
		pc = 0
		map = {}

		for b in self.blocks:
			for l in b.labels:
				map[l] = pc

			pc = pc + b.size + b.branch_size

		delta = True
		while delta:
			pc = 0
			delta = False

			for b in self.blocks:

				pc = pc + b.size
				l = b.branch_target
				if not l: continue

				if b.branch_long:
					pc = pc + b.branch_size
					continue

				target = map[l]
				diff = target-(pc+1)
				pc = pc + 2

				if diff < -128 or diff > 127:
					delta = True
					b.branch_long = True
					if b.branch_type == 'bra':
						b.branch_type = 'brl'
						b.branch_size = 3
						fudge = 1
					else:
						b.branch_size = 5
						fudge = 3

					for x in map:
						if map[x] >= pc:
							map[x] = map[x] + fudge


		for b in self.blocks:

			l = b.branch_target
			if not l: continue
			t = b.branch_type

			if b.branch_long:
				if b.branch_type not in ('bra', 'brl'):
					t = self.__inverted_branch[t]
					b.instr.append("\t{} *+5".format(t))
				b.instr.append("\tbrl " + l)
			else:
				b.instr.append("\t{} {}".format(t, l))

			b.size = b.size + b.branch_size

	def finish(self,io):
		onoff = ("on", "off")
		self.b = None
		self.merge_rts()
		self.merge_labels()
		self.reify_branches()

		self.header(io)

		mx = 0b11
		io.write("\tlongi on\n")
		io.write("\tlonga on\n")

		for b in self.blocks:
			for l in b.labels: io.write(l + "\tanop\n")

			# io.write(f"mx: {b.mx}\n")
			mxdiff = mx ^ b.mx
			if mxdiff:
				if mxdiff & 0b01:
					io.write("\tlongi " + onoff[mx & 0b01] + "\n")
				if mxdiff & 0b10:
					io.write("\tlonga " + onoff[(mx & 0b10) >> 1] + "\n")

				mx = b.mx

			for i in b.instr: io.write(i + "\n")
		self.footer(io)

		self.blocks = []
		self.mx = 0b11
		self.new_block()

	def header(self, io):
		io.write("* generated " + asctime() + "\n\n")
		io.write("\tcase on\n\n");
		io.write("dummy\tSTART\n\tEND\n\n")
		io.write(self.name + "\tSTART\n\n")
		io.write("cp\tequ 5\n")

		txt = """
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
			"""
		io.write(indent(dedent(txt),"\t"))
		io.write("\n_action\tanop\n")
		io.write("\tldx #0\n\n")


	def footer(self, io):
		io.write("\tEND\n")
