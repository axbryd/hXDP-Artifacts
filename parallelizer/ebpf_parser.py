"""
                    eBPF instruction encoding

msb                                                                   lsb
+-------------+-------+-------+----------------+------------------------+
|opcode       |dst    |src    |offset          |immediate               |
+-------------+-------+-------+----------------+------------------------+
0            7 8    11 12   15 16            31 32                     63
"""
from enum import IntEnum

# eBPF instruction field masks
OPCODE_MASK = 0xff
DST_MASK = 0xf
SRC_MASK = 0xf
OFFSET_MASK = 0xffff
IMMEDIATE_MASK = 0xffffffff

# eBPF instruction field shift for read (msb)
OPCODE_SHIFT = 0
DST_SHIFT = 8
SRC_SHIFT = 12
OFFSET_SHIFT = 16
IMMEDIATE_SHIFT = 32

# eBPF instruction field shift for write (lsb)
OPCODE_SHIFT_MOD = 56
DST_SHIFT_MOD = 48
SRC_SHIFT_MOD = 52
OFFSET_SHIFT_MOD = 32
IMMEDIATE_SHIFT_MOD = 0

# eBPF standard opcodes
BRANCH_OPCODE = {0x05, 0x15, 0x1d, 0x25, 0x2d, 0x35, 0x3d, 0xa5, 0xad, 0xb5, 0xbd, 0x45, 0x4d, 0x55, 0x5d, 0x65, 0x6d,
                 0x75, 0x7d, 0xc5, 0xcd, 0xd5, 0xdd, 0x85, 0x95, 0x96}
BRANCH_NO_INPUT = {0x05, 0x85, 0x95, 0x96}  # immediate jumps, calls and exit
IF_BRANCH = BRANCH_OPCODE.difference(BRANCH_NO_INPUT)  # jumps
IF_GREATER = {0x2d, 0x3d}  # if rx >[=] ry jumps
CALL_OPCODE = 0x85
GOTO_OPCODE = 0x05
EXIT = {0x95, 0x96}

MOV = 0xbf
ALU_ADD_IMM = {0x07, 0x8f}
ALU_ADD_REG = {0x0f}
NOP = 0x0
ALU = {0x07, 0x0f, 0x17, 0x1f, 0x27, 0x2f, 0x37, 0x3f, 0x47, 0x4f, 0x57, 0x5f, 0x67, 0x6f, 0x77, 0x7f, 0x87, 0x97, 0x9f,
       0xa7, 0xaf, 0xb7, 0xbf, 0xc7, 0xcf, 0x04, 0x0c, 0x14, 0x1c, 0x24, 0x2c, 0x34, 0x3c, 0x44, 0x4c, 0x54, 0x5c, 0x64,
       0x6c, 0x74, 0x7c, 0x84, 0x94, 0x9c, 0xa4, 0xac, 0xb4, 0xbc, 0xc4, 0xcc}

# Sephirot ISA extension opcodes
# - load(store)48
LOAD48 = 0x59
STORE48 = 0x5a
# - mov-alu
CORRESPONDENT = {0x07: 0x8f, 0x17: 0xd7, 0x47: 0xdf, 0x57: 0xe7,
                 0x67: 0xef, 0x77: 0xf7, 0x57: 0xff, 0x04: 0x8c, 0x14: 0xe4, 0x64: 0xec, 0x74: 0xf4, 0xa4: 0xfc}
MOV_ALU = {CORRESPONDENT[x] for x in CORRESPONDENT}
MOV_IMM = 0xb7
# - mov-exit
MOV_EXIT = 0x96

# Instructions having input operand on dst field only
ONLY_DST_INPUT = {0x07, 0x17, 0x27, 0x37, 0x47, 0x57, 0x67, 0x77, 0x87, 0x97, 0xa7, 0xc7, 0x04, 0x14, 0x24, 0x34, 0x44,
                  0x54, 0x64, 0x74, 0x84, 0x94, 0xa4, 0xc4, 0xd4, 0xdc, 0x62, 0x6a, 0x72, 0x7a, 0x15, 0x25, 0x35, 0xa5,
                  0xb5, 0x45, 0x55, 0x65, 0x75, 0xc5, 0xd5}
# Instructions having input operand on both src & dst fields
DST_SRC_INPUT = {0x0f, 0x1f, 0x2f, 0x3f, 0x4f, 0x5f, 0x6f, 0x7f, 0x9f, 0xaf, 0xcf, 0x0c, 0x1c, 0x2c, 0x3c, 0x4c, 0x5c,
                 0x6c, 0x7c, 0x9c, 0xac, 0xcc, 0x63, 0x6b, 0x73, 0x7b, 0x1d, 0x2d, 0x3d, 0xad, 0xbd, 0x4d, 0x5d, 0x6d,
                 0x7d, 0xcd, 0xdd}.union({STORE48})
# Instructions having input operand only on src field
ONLY_SRC_INPUT = {0xbf, 0xbc, 0x61, 0x69, 0x71, 0x79}.union(MOV_ALU).union({LOAD48})
# No input instructions
NO_INPUT = {0xb7, 0xb4, 0x18, 0x05, 0x85, 0x95, 0x96}

# Instructions with no output operand
NO_OUTPUT = BRANCH_OPCODE.union({0x62, 0x6a, 0x72, 0x7a, 0x63, 0x6b, 0x73, 0x7b})

BRANCH_NO_OFFSET = {0x85, 0x95, 0x96}  # branch instructions without offset

# Memory instructions
LOAD_OPCODE = {0x18, 0x20, 0x28, 0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x61, 0x69, 0x71, 0x79}.union({LOAD48})
STORE_OPCODE = {0x62, 0x6a, 0x72, 0x7a, 0x63, 0x6b, 0x73, 0x7b}.union({STORE48})

# Memory instructions to size in B
LOAD_TO_SIZE = {0x61: 32, 0x69: 16, 0x71: 8, 0x79: 64, 0x59: 48}
STORE_TO_SIZE = {0x63: 32, 0x6b: 16, 0x73: 8, 0x7b: 64, 0x5a: 48}

# Candidate mem instructions to be transformed in load48/store48
LOAD_TO_SIZE48 = {0x69: 16, 0x71: 8}
STORE_TO_SIZE48 = {0x6b: 16, 0x73: 8}


class XDPAction(IntEnum):
    ABORTED = 0,
    DROP = 1,
    PASS = 2,
    TX = 3


def is_if_greater_eq(unpkd):
    return unpkd["opcode"] in IF_GREATER


def is_branch(unpacked_instruction):
    return unpacked_instruction["opcode"] in BRANCH_OPCODE


def is_call(unpacked_instruction):
    return unpacked_instruction["opcode"] == CALL_OPCODE


def is_goto(unpacked_instruction):
    return unpacked_instruction["opcode"] == GOTO_OPCODE


def is_jump(unpkd):
    return unpkd["opcode"] in BRANCH_OPCODE - EXIT.union({CALL_OPCODE})


def is_exit(unpkd):
    return unpkd["opcode"] in EXIT


def is_mov_exit(unpkd):
    return unpkd["opcode"] == MOV_EXIT


def is_alu(unpkd):
    return unpkd["opcode"] in ALU


def is_alu_add_imm(unpkd):
    return unpkd["opcode"] in ALU_ADD_IMM


def is_alu_add_reg(unpkd):
    return unpkd["opcode"] in ALU_ADD_REG


def is_mov_imm(unpkd):
    return unpkd["opcode"] == MOV_IMM


def is_mov(unpkd):
    return unpkd["opcode"] == MOV


def get_correspondent(opcode):
    return CORRESPONDENT.get(opcode)


def big_to_little(instruct, size=8, signed=False):
    return int.from_bytes(instruct.to_bytes(size, byteorder='big', signed=signed), byteorder='little', signed=signed)


def little_to_big(instruct, size=8, signed=False):
    return int.from_bytes(instruct.to_bytes(size, byteorder='little', signed=signed), byteorder='big', signed=signed)


def twos_comp(val, bits):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)  # compute negative value
    return val  # return positive value as is


def modify_offset(instruct, offset):
    offset = little_to_big(offset, 2, True)

    for i in range(16):
        bit = ((offset & (1 << i)) != 0)
        if bit == 0:
            instruct &= ~(1 << (i + OFFSET_SHIFT_MOD))
        else:
            instruct |= (1 << (i + OFFSET_SHIFT_MOD))
    return instruct


def copy_immediate(instruct, immediate):
    immediate = little_to_big(immediate, size=4)

    for i in range(32):
        bit = ((immediate & (1 << i)) != 0)
        if bit == 0:
            instruct &= ~(1 << (i + IMMEDIATE_SHIFT_MOD))
        else:
            instruct |= (1 << (i + IMMEDIATE_SHIFT_MOD))
    return instruct


def modify_register(instruct, register, shift):
    register = little_to_big(register, size=1)

    for i in range(4):
        bit = ((register & (1 << i)) != 0)
        if bit == 0:
            instruct &= ~(1 << (i + shift))
        else:
            instruct |= (1 << (i + shift))
    return instruct


def extract_field(instruct, mask, shift):
    return little_to_big(instruct) >> shift & mask


def unpack_instruction(instruct):
    return {"opcode": extract_field(instruct, OPCODE_MASK, OPCODE_SHIFT),
            "dst": extract_field(instruct, DST_MASK, DST_SHIFT),
            "src": extract_field(instruct, SRC_MASK, SRC_SHIFT),
            "offset": twos_comp(extract_field(instruct, OFFSET_MASK, OFFSET_SHIFT), 16),
            "immediate": extract_field(instruct, IMMEDIATE_MASK, IMMEDIATE_SHIFT)
            }


def get_inputs(unpacked_instruction):
    if unpacked_instruction["opcode"] in ONLY_SRC_INPUT:
        return [unpacked_instruction["src"]]
    elif unpacked_instruction["opcode"] in ONLY_DST_INPUT:
        return [unpacked_instruction["dst"]]
    elif unpacked_instruction["opcode"] in DST_SRC_INPUT:
        return [unpacked_instruction["src"], unpacked_instruction["dst"]]
    elif is_exit(unpacked_instruction):
        return [0]
    else:
        return []


def del_src(instruct):
    return modify_register(instruct, 0, SRC_SHIFT_MOD)


def set_opcode(instruct, opcode):
    for i in range(8):
        bit = ((opcode & (1 << i)) != 0)
        if bit == 0:
            instruct &= ~(1 << (i + OPCODE_SHIFT_MOD))
        else:
            instruct |= (1 << (i + OPCODE_SHIFT_MOD))
    return instruct


def set_inputs(instruct, inputs):
    unpkd = unpack_instruction(instruct)
    if unpkd["opcode"] in ONLY_SRC_INPUT:
        return modify_register(instruct, inputs[0], SRC_SHIFT_MOD)
    elif unpkd["opcode"] in ONLY_DST_INPUT:
        return modify_register(instruct, inputs[0], DST_SHIFT_MOD)
    elif unpkd["opcode"] in DST_SRC_INPUT:
        instruct = modify_register(instruct, inputs[0], SRC_SHIFT_MOD)
        return modify_register(instruct, inputs[1], DST_SHIFT_MOD)


def set_output(instruct, output):
    return modify_register(instruct, output, DST_SHIFT_MOD)


def get_output(unpacked_instruction):
    if unpacked_instruction["opcode"] in NO_OUTPUT:
        return None
    else:
        return unpacked_instruction["dst"]


def is_load(unpacked_instruction):
    return unpacked_instruction["opcode"] in LOAD_OPCODE


def is_store(unpacked_instruction):
    return unpacked_instruction["opcode"] in STORE_OPCODE


def is_no_input_branch(unpacked_instruction):
    return unpacked_instruction["opcode"] in BRANCH_NO_INPUT


def is_no_offset_branch(unpacked_instruction):
    return unpacked_instruction["opcode"] in BRANCH_NO_OFFSET


def is_nop(unpacked_instruction):
    return unpacked_instruction["opcode"] == NOP


def print_unpkd(unpkd, n=None):
    number = str(n) + ": " if n is not None else ""
    print(number + "|0x{:02x}".format(unpkd["opcode"]) + "|0x{:01x}".format(
        unpkd["dst"]) + "|0x{:01x}".format(unpkd["src"]) +
          "|0x{:04x}".format(unpkd["offset"]) +
          "|0x{:08x}".format(
              unpkd["immediate"]) + "|")


def is_no_input(unpkd):
    return unpkd["opcode"] not in NO_INPUT


def is_optimizable_mov_alu(unpkd):
    return unpkd["opcode"] in CORRESPONDENT


def is_optimized_mov_alu(unpkd):
    return unpkd["opcode"] in MOV_ALU


def load_to_size(unpkd):
    return LOAD_TO_SIZE[unpkd["opcode"]] if unpkd["opcode"] in LOAD_TO_SIZE else None


def store_to_size(unpkd):
    return STORE_TO_SIZE[unpkd["opcode"]] if unpkd["opcode"] in STORE_TO_SIZE else None


def is_a_load48(unpkd):
    return unpkd["opcode"] in LOAD_TO_SIZE48


def is_a_store48(unpkd):
    return unpkd["opcode"] in STORE_TO_SIZE48


def is_if_branch(unpkd):
    return unpkd["opcode"] in IF_BRANCH
