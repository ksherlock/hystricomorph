from textwrap import indent, dedent
from time import asctime

class Block(object):
	def __init__(self):
		self.size = 0
		self.bne = None
		self.bne_long = False
		self.labels = []
		self.instr = []
		self.rts = False
		self.mx = 0b11

	def empty(self):
		return len(self.instr) == 0 and self.bne == None

class Assembler(object):
	def __init__(self, name):
		self.name = name
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
		mx = 0b11
		if self.b:
			mx = self.b.mx
		self.b = Block()
		self.b.mx = mx

		self.blocks.append(self.b)

	def bne(self, l):
		self.b.bne = l
		self.new_block()

	def emit(self, op, size):
		self.b.size = self.b.size + size
		self.b.instr.append("\t" + op)

	def mx_common(self, onoff, mask):
		mx = oldmx = self.b.mx

		if onoff: mx |= mask
		else: mx &= ~mask

		if mx == oldmx: return

		if not self.b.empty():
			self.new_block()

		self.b.mx = mx


	def longm(self, onoff):
		self.mx_common(onoff, 0b10)

	def longx(self, onoff):
		self.mx_common(onoff, 0b01)

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
			if b.bne:
				b.bne = map[b.bne]

	def reify_branches(self):
		# in practice all branches are forward
		# could be clever and try to find a backwards rts branch island
		pc = 0
		map = {}

		for b in self.blocks:
			for l in b.labels:
				map[l] = pc

			pc = pc + b.size
			if b.bne: pc = pc + 2 # optimist

		delta = True
		while delta:
			pc = 0
			delta = False

			for b in self.blocks:

				pc = pc + b.size
				l = b.bne
				if not l: continue

				if b.bne_long:
					pc = pc + 5
					continue

				target = map[l]
				diff = target-(pc+1)
				pc = pc + 2

				if diff < -128 or diff > 127:
					delta = True
					b.bne_long = True

					for x in map:
						if map[x] >= pc:
							map[x] = map[x] + 3


		for b in self.blocks:

			l = b.bne
			if not l: continue
			if b.bne_long:
				b.instr.append("\tbeq *+5")
				b.instr.append("\tbrl " + l)
				b.size = b.size + 5
			else:
				b.instr.append("\tbne " + l)
				b.size = b.size + 2


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
