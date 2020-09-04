import re

INSTR_REGEX = '([A-Fa-f0-9]{2}( )){7}([A-Fa-f0-9]{2})(( )([A-Fa-f0-9]{2}( )){7}([A-Fa-f0-9]{2}))?'
COMMENTS_REGEX = '(;).*?'


def read_file(filename):
    # parse file and returns the list of instructions as integers, and the list of str mnemonics

    program_bin = []
    program_str = []
    for line in open(filename, 'r'):
        if not re.search(COMMENTS_REGEX, line):  # ignore comment line
            instr_match = re.search(INSTR_REGEX, line)

            if instr_match:
                instr_s = line[instr_match.regs[0][1]:].lstrip().replace("\n", "")
                label = re.search("(<)\w+(>)", instr_s)
                if label:
                    instr_s = instr_s[:label.regs[0][0]]

                program_str.append(instr_s)


                program_bin.append(int(instr_match.group(0).replace(' ', '')[:16], 16))

                if len(instr_match.group(0).replace(' ', '')) > 16:
                    program_bin.append(0)
                    program_str.append("NOP")

    return program_bin, program_str


def print_line(line):
    bins = "{0:64b}".format(line).replace(" ", "0")
    print("|"+bins[:8]+"|"+bins[8:12]+"|"+bins[12:16]+"|"+bins[16:32]+"|"+bins[32:64]+"|")

