from enum import Enum
import networkx as nx
from ebpf_parser import *
import re
import TableIt

from optimizations.Load48Store48 import Load48Store48
from optimizations.LoadStore48 import LoadStore48
from optimizations.MemsetToZero import MemsetToZero
from register_cache import *

NUM_LANES = 4
DEFAULT_BRANCH_LANE = 0
BRANCH_ALL_LANES = True  # branches can be assigned to any lane
LANE_FORWARD_CONSTRAINT = True  # depending instructions scheduled back to back must be on the same lane

# ABI physical register constraint
NUM_PHY_REGS = 10
CALLS_REGS = list(range(1, 6))
STACK_REG = 10
RETURN_REG = 0

ALL_CALL_MODIFIED = list(CALLS_REGS)
ALL_CALL_MODIFIED.extend([RETURN_REG])

REMOVE_MEM_BOUNDARY_CHECKS = False  # remove memory boundary checks
ADVANCED_OPTIMIZATIONS = True  # enable advanced optimizations (e.g., LoadStore48, Load48Store48, MemsetToZero)
CODE_MOVEMENT = False  # enable code movement optimization

# debug prints and graph plot
DEBUG_DRAW_CFG = False  # draw program CFG
DEBUG_PRINT_BLOCKS_PRE_OPT = False  # print blocks before local optimization
DEBUG_PRINT_BLOCKS_PRE_SCHED = False  # print blocks before scheduling (after local optimizations)
DEBUG_DRAW_DDG = False  # draw block DDG
DEBUG_PRINT_RESOURCE_TABLE = True  # print the final resource table (with instructions in their str representation)

TYPE = "type"
START = "start"
LEN = "len"
INSTRUCTIONS = "instructions"
OUT_OPERANDS = "out_operands"
IN_OPERANDS = "in_operands"
DEFS = "defs"
USES = "uses"
SYM_TABLE = "sym_table"
TNEXT = "tnext"
FNEXT = "fnext"
RESOURCE_TABLE = "resource_table"

INSTR_B = "instr_b"
INSTR_S = "instr_s"
INPUTS = "inputs"
OUTPUT = "output"
ORIG_POS = "orig_pos"
JMP_BLOCK = "jmp_block"
PENDING_DEPS = "pending_deps"

SYM_NAME = "sym_name"
LIVE = "live"
NEXT_USE = "next_use"

OFFSET = "offset"
BRANCHES = "branches"

BLOCK = "block"
TIME = "time"
LANE = "lane"

SYMBOLS = "symbols"


class BlockType(Enum):
    START = 0,  # entry point for the program (pseudoblock)
    EXIT = 1,  # exit point for the program (pseudoblock)
    BASIC = 2,  # actual block with code
    CALL = 3,  # helper function call pseudoblock
    DISABLED = 4  # empty block after optimizations (pseudoblock)


class Optimizer:
    def __init__(self, program_bin, program_str, filename=None, branch_all_lanes=BRANCH_ALL_LANES,
                 lane_forward_constraint=LANE_FORWARD_CONSTRAINT,
                 remove_mem_boundary_checks=REMOVE_MEM_BOUNDARY_CHECKS,
                 advanced_optimizations=ADVANCED_OPTIMIZATIONS,
                 code_movement=CODE_MOVEMENT,
                 debug_draw_cfg=DEBUG_DRAW_CFG,
                 debug_print_blocks_pre_sched=DEBUG_PRINT_BLOCKS_PRE_SCHED,
                 debug_print_blocks_pre_opt=DEBUG_PRINT_BLOCKS_PRE_OPT,
                 debug_draw_ddg=DEBUG_DRAW_DDG,
                 debug_print_resource_table=DEBUG_PRINT_RESOURCE_TABLE):
        # params
        self.filename = filename  # filename, used for debugging
        self.branch_all_lanes = branch_all_lanes
        self.lane_forward_constraint = lane_forward_constraint
        self.remove_mem_boundary_checks = remove_mem_boundary_checks
        self.advanced_optimizations = advanced_optimizations
        self.code_movement = code_movement
        self.debug_draw_cfg = debug_draw_cfg
        self.debug_print_blocks_pre_sched = debug_print_blocks_pre_sched
        self.debug_print_blocks_pre_opt = debug_print_blocks_pre_opt
        self.debug_draw_ddg = debug_draw_ddg
        self.debug_print_resource_table = debug_print_resource_table

        self.program_bin = program_bin  # as int array
        self.program_str = program_str  # as str array

        self.__reinit_block_info_data_structs()

        self.resource_table = [[None for i in range(NUM_LANES)] for i in
                               self.program_bin]  # global resource table (each lane at each clock cycle)

        self.bound_check_cache = {"pkt_act_reg": None,  # reg containing action if default not defined
                                  "pkt_act": None,
                                  # action, if pkt_act is None is the default action of the program (mov-exit)
                                  "ctx": (None, 0),  # pointer to xdp context
                                  "ctx_data": (None, 0),  # ctx->data
                                  "ctx_data_end": (None, 0),  # ctx->data_end
                                  "ctx_data_+_offset": (None, None, 0)  # (reg_name, offset, valid_until_line)
                                  }  # (reg_name, valid_until_line)

        # stats
        self.mov_alu_compressed = 0
        self.movi_exit_compressed = 0

        # output symbols in use
        self.reg_cache = RegisterCache()  # in use registers cache

    def __find_branches(self):
        # This method do a forward pass to the ebpf assembly and identifies branches (divided in jumps, calls & exits)

        for i in range(len(self.program_bin)):
            unpkd = unpack_instruction(self.program_bin[i])

            if is_jump(unpkd):
                self.jumps_indexes.add(i)

                target = i + unpkd[OFFSET] + 1

                if target >= len(self.program_bin):
                    print("\033[91mInvalid offset (outside program) for branch instruction " + "0x{:16x}".format(
                        self.program_bin[i]))
                    exit(-1)

                if target not in self.jumps_targets_indexes:
                    self.jumps_targets_indexes[target] = {BRANCHES: [i]}
                else:
                    self.jumps_targets_indexes[target][BRANCHES].append(i)

            elif is_call(unpkd):
                self.calls_indexes.add(i)

            elif is_exit(unpkd):
                self.exits_indexes.add(i)

    def __parse_instruction(self, pos):
        # This method parses the instruction unpacking its input(output) operands, saving its original pos in the
        # ebpf asm (global id in the compiler), the landing block (if it's a jump) and the # of pending instructions
        # to be evaluated for the input operands

        instr_b = self.program_bin[pos]
        instr_s = self.program_str[pos]

        unpkd = unpack_instruction(instr_b)

        return {INSTR_B: instr_b,
                INSTR_S: instr_s,
                INPUTS: [{SYM_NAME: op, LIVE: False, NEXT_USE: None} for op in get_inputs(unpkd)],
                OUTPUT: {SYM_NAME: get_output(unpkd), LIVE: False, NEXT_USE: None} if get_output(
                    unpkd) is not None and not is_nop(unpkd) else None,
                ORIG_POS: pos,
                JMP_BLOCK: None,
                PENDING_DEPS: len(get_inputs(unpkd))
                }

    def __leader_to_block(self, leader):
        # This method resolves from the leader instruction id the correspondent block

        for b in range(len(self.blocks)):
            if self.blocks[b][START] == leader:
                return b
        if leader == len(self.program_bin) - 1:
            return len(self.blocks) - 1

        print("\033[91m[optimizer_core] __leader_to_block: invalid leader instruction " + str(leader))
        exit(-1)

    def __inst_to_block(self, inst_pos):
        # This method resolves from the instruction id to the correspondent block

        found = False
        for b in range(len(self.blocks)):
            for inst in self.blocks[b][INSTRUCTIONS]:
                if inst[ORIG_POS] == inst_pos:
                    found = True
                    break
            if found:
                return b

        print("\033[91m[optimizer_core] __inst_to_block: invalid instruction " + str(inst_pos))
        exit(-1)

    def __find_blocks(self):
        # This method finds block boundaries with boundaries found by __find_branches

        calls_exits = self.calls_indexes.union(self.exits_indexes) - {len(self.program_bin) - 1}

        leaders = sorted(
            set(map(lambda x: x + 1 if x < len(self.program_bin) - 1 else x,
                    self.jumps_indexes.union(calls_exits))).union(
                self.jumps_targets_indexes.keys()))  # leader instructions from branches boundaries

        if len(leaders) and leaders[0] > 0:
            self.blocks.append({TYPE: BlockType.BASIC,
                                START: 0,
                                LEN: leaders[0],
                                INSTRUCTIONS: [],
                                OUT_OPERANDS: {},  # symbols live in exit (living outputs for the block)
                                IN_OPERANDS: {},  # input symbols for the block
                                DEFS: {},  # defined symbols
                                USES: {},  # used symbols
                                SYM_TABLE: {},  # sym_name: {LIVE: True|False, NEXT_USE: i} (i index in seq program)
                                TNEXT: [],
                                FNEXT: None,
                                })

        for i in range(len(leaders)):
            length = leaders[i + 1] - leaders[i] if i < len(leaders) - 1 else len(self.program_bin) - leaders[i]

            self.blocks.append({TYPE: BlockType.BASIC,
                                START: leaders[i],
                                LEN: length,
                                INSTRUCTIONS: [],
                                OUT_OPERANDS: {},  # symbols live in exit (living outputs for the block)
                                IN_OPERANDS: {},  # input symbols for the block
                                DEFS: {},  # defined symbols
                                USES: {},  # used symbols
                                SYM_TABLE: {},  # sym_name: {LIVE: True|False, NEXT_USE: i} (i index in seq program)
                                TNEXT: [],
                                FNEXT: None,
                                })

            last = unpack_instruction(self.program_bin[leaders[i] + length - 1])
            if is_call(last):
                self.blocks.append({TYPE: BlockType.CALL,
                                    START: leaders[i],
                                    LEN: 0,
                                    INSTRUCTIONS: [],
                                    OUT_OPERANDS: {},  # symbols live in exit (living outputs for the block)
                                    IN_OPERANDS: {},  # input symbols for the block
                                    DEFS: {},  # defined symbols
                                    USES: {},  # used symbols
                                    SYM_TABLE: {},  # sym_name: {LIVE: True|False, NEXT_USE: i} (i index in seq program)
                                    TNEXT: [],
                                    FNEXT: None,
                                    })

        self.blocks.append({TYPE: BlockType.EXIT,
                            START: len(self.program_bin),
                            LEN: 0,
                            INSTRUCTIONS: [],
                            OUT_OPERANDS: {},  # symbols live in exit (living outputs for the block)
                            IN_OPERANDS: {},  # input symbols for the block
                            DEFS: {},  # defined symbols
                            USES: {},  # used symbols
                            SYM_TABLE: {},  # sym_name: {LIVE: True|False, NEXT_USE: i} (i index in seq program)
                            TNEXT: [],
                            FNEXT: None,
                            })

    def __parse_blocks(self):
        # This method uses boundaries fond by __find_blocks and divides the eBPF asm in blocks
        # and parses each instruction
        # FNEXT: default next block, TNEXT: next block if the jump is taken

        for b in range(1, len(self.blocks) - 1):
            blck = self.blocks[b]

            for i in range(blck[START], blck[START] + blck[LEN]):
                instr = self.__parse_instruction(i)

                blck[INSTRUCTIONS].append(instr)
                self.schedule[i][BLOCK] = b

            blck[FNEXT] = b + 1

            if blck[TYPE] == BlockType.CALL:
                blck[FNEXT] = b + 1
                blck[TNEXT] = []

            else:
                last = unpack_instruction(blck[INSTRUCTIONS][-1][INSTR_B])
                if is_call(last):
                    blck[TNEXT].append(b + 1)
                    blck[FNEXT] = None
                elif is_jump(last):
                    blck[TNEXT].append(self.__leader_to_block(blck[START] + blck[LEN] + last[OFFSET]))
                    blck[INSTRUCTIONS][-1][JMP_BLOCK] = blck[TNEXT][-1]
                    if is_goto(last):
                        blck[FNEXT] = None
                elif is_exit(last):
                    blck[TNEXT].append(len(self.blocks) - 1)
                    blck[FNEXT] = None

    def __build_flow_graph(self):
        # Build program CFG using information computed by __parse_blocks, computing dominators and postdominators
        # for each block

        self.flow_graph = nx.DiGraph()
        edges = []
        for b in range(len(self.blocks)):
            if self.blocks[b][TYPE] == BlockType.START:
                self.flow_graph.add_node(b, shape="square", style="filled", fillcolor="royalblue", label='START')
            elif self.blocks[b][TYPE] == BlockType.EXIT:
                self.flow_graph.add_node(b, shape="square", style="filled", fillcolor="royalblue", label='EXIT')
            elif self.blocks[b][TYPE] == BlockType.CALL:
                self.flow_graph.add_node(b, shape="square", style="filled", fillcolor="orange", label='CALL')
            else:
                self.flow_graph.add_node(b, label="B" + str(b))

            for dst_blck in self.blocks[b][TNEXT]:
                edges.append((b, dst_blck))
            if self.blocks[b][FNEXT] is not None:
                edges.append((b, self.blocks[b][FNEXT]))

        self.flow_graph.add_edges_from(edges)

        if self.code_movement:  # TODO: minor performance improvement, disabled for now
            self.dominators = self.__compute_dominators(self.flow_graph)
            self.postdominators = self.__compute_dominators(self.flow_graph.reverse())

    def __reinit_block_info_data_structs(self):
        # This method reinit the compiler data structures containing info on blocks. Must be called before
        # analyze_program_cfg

        self.jumps_indexes = set()  # indexes in the original program
        self.calls_indexes = set()
        self.exits_indexes = set()

        self.jumps_targets_indexes = {}  # target_index -> BRANCHES: [x, y, ...]

        self.blocks = [{TYPE: BlockType.START,
                        START: -1,
                        LEN: 0,
                        INSTRUCTIONS: [],
                        OUT_OPERANDS: {},  # symbols live in exit (living outputs for the block)
                        IN_OPERANDS: {},  # input symbols for the block
                        DEFS: {},  # defined symbols
                        USES: {},  # used symbols
                        SYM_TABLE: {},  # sym_name: {LIVE: True|False, NEXT_USE: i} (i index in seq program)
                        TNEXT: [],
                        FNEXT: 1,
                        }]

        self.schedule = [{BLOCK: None, TIME: i, LANE: None} for i in
                         range(len(self.program_bin))]  # global schedule for each instruction (block, time, lane)

    def __analyze_program_cfg(self):
        # This method analyze the eBPF asm program blocks and computes CFG

        self.__find_branches()  # fw pass to find branch boundaries
        self.__find_blocks()  # fw pass to identify basic blocks
        self.__parse_blocks()  # fw pass parse instructions and divide in basic blocks
        self.__build_flow_graph()  # fw pass to build CFG

    def __analyze_program_data_deps(self):
        # This method analyze the eBPF asm program blocks and computes CFG

        self.__compute_liveness_global()  # compute liveness between blocks
        self.__compute_next_use_liveness_local()  # compute liveness inside each basic block

    def optimize(self):
        self.__analyze_program_cfg()

        # DEBUG: print program blocks
        if self.debug_print_blocks_pre_opt:
            self.__print_blocks()

        # DEBUG: draw program CFG
        if self.debug_draw_cfg:
            p = nx.drawing.nx_pydot.to_pydot(self.flow_graph)
            p.write_png(self.filename + '_CFG.png' if self.filename is not None else "flow_graph.png")

        # Local optimizations
        self.__local_optimizations()  # mov-alu & mov-exit compression
        self.__analyze_program_data_deps()

        if self.remove_mem_boundary_checks:
            self.__remove_memory_boundaries_checks()

        if self.advanced_optimizations:
            self.__advanced_optimizations()

        # After local optimizations CFG and data deps must be recomputed
        if self.remove_mem_boundary_checks or self.__advanced_optimizations():
            self.__reinit_block_info_data_structs()
            self.__analyze_program_cfg()
            self.__analyze_program_data_deps()

        # Register renaming pass in order to remove WAW dependencies
        # self.__pre_schedule_register_assignment()

        if self.debug_print_blocks_pre_sched:
            self.__print_blocks()

        # Scheduling
        self.__global_schedule()

        print("\nLocal Optimizations:")
        print(" ~ mov-alu: " + str(self.mov_alu_compressed))
        print(" ~ movi-exit: " + str(self.movi_exit_compressed))

        print("\nBranches found:")
        print(" ~ jumps:         " + str(sorted(self.jumps_indexes)))
        print(" ~ calls:         " + str(sorted(self.calls_indexes)))
        print(" ~ exits:         " + str(sorted(self.exits_indexes)))
        print(" ~ jumps targets: " + str(sorted(self.jumps_targets_indexes.keys())))
        print("\n")

        self.__fix_branch_offsets()  # Since branches are now on different positions (rows)

    def __print_blocks(self):
        # This method prints all the blocks (with their instructions) and used operands

        print("START block\n")
        for b in range(1, len(self.blocks) - 1):
            blck = self.blocks[b]
            print("B" + str(b) + " - " + str(blck[TYPE])[10:])
            print("------------------")

            for instr in blck[INSTRUCTIONS]:
                print(instr[INSTR_S])

            print()
            print("USE: " + str(blck[USES]))
            print("DEF: " + str(blck[DEFS]))
            print("IN: " + str(blck[IN_OPERANDS]))
            print("OUT: " + str(blck[OUT_OPERANDS]))

            if blck[TYPE] == BlockType.CALL:
                print("... helper function code ...")

            print()
        print("EXIT block\n")

    def __compute_liveness_global(self):
        # This method uses info calculated by __compute_liveness_global for computing data dependencies inside each
        # block

        b = 0
        for blck in self.blocks:
            blck[USES] = {}
            blck[DEFS] = {}
            blck[OUT_OPERANDS] = {}
            blck[IN_OPERANDS] = {}
            for instr in blck[INSTRUCTIONS]:
                if is_call(unpack_instruction(instr[INSTR_B])):
                    id = unpack_instruction(instr[INSTR_B])["immediate"]
                    for inp in self.__call_to_regs(id):  # input regs from ABI
                        if inp not in blck[DEFS]:
                            blck[USES][inp] = instr[ORIG_POS]
                    blck[DEFS][0] = instr[ORIG_POS]  # r0 as out reg
                    continue
                for instr_in in instr[INPUTS]:
                    if instr_in[SYM_NAME] not in blck[DEFS]:
                        blck[USES][instr_in[SYM_NAME]] = instr[ORIG_POS]
                if instr[OUTPUT] is not None:
                    blck[DEFS][instr[OUTPUT][SYM_NAME]] = instr[ORIG_POS]
            b += 1
        fg_rev = self.flow_graph.reverse()
        blocks = list(nx.topological_sort(fg_rev))
        changed = True
        while changed:
            changed = False

            for b in blocks:
                blck = self.blocks[b]
                last_in, last_out = self.__light_copy(blck[IN_OPERANDS]), self.__light_copy(blck[OUT_OPERANDS])

                blck[IN_OPERANDS] = self.__union_dicts(self.__diff_dicts(blck[OUT_OPERANDS], blck[DEFS]), blck[USES])

                successors = list(self.flow_graph.successors(b))
                if len(successors) > 0:
                    for s in successors:
                        succ = self.blocks[s]
                        blck[OUT_OPERANDS] = self.__union_dicts(succ[IN_OPERANDS], blck[OUT_OPERANDS])

                if last_in.keys() != blck[IN_OPERANDS].keys() or last_out.keys() != blck[OUT_OPERANDS].keys():
                    changed = True

    def __compute_next_use_liveness_local(self):
        # This method uses info calculated by __compute_liveness_global for computing data dependencies inside each
        # block

        b = 0
        for blck in self.blocks:
            b += 1
            if blck[TYPE] != BlockType.BASIC:  # only BASIC block contain instructions
                continue

            blck[SYM_TABLE] = {}  # sym_name -> LIVE, NEXT_USE
            for instr in reversed(blck[INSTRUCTIONS]):
                if instr[OUTPUT] is not None:
                    if instr[OUTPUT][SYM_NAME] not in blck[SYM_TABLE]:
                        if instr[OUTPUT][SYM_NAME] not in blck[OUT_OPERANDS]:
                            blck[SYM_TABLE][instr[OUTPUT][SYM_NAME]] = {LIVE: False, NEXT_USE: None}
                        else:
                            blck[SYM_TABLE][instr[OUTPUT][SYM_NAME]] = {LIVE: True, NEXT_USE: blck[OUT_OPERANDS][
                                instr[OUTPUT][SYM_NAME]]}
                            instr[OUTPUT][LIVE], instr[OUTPUT][NEXT_USE] = True, blck[OUT_OPERANDS][
                                instr[OUTPUT][SYM_NAME]]
                    else:
                        entry = blck[SYM_TABLE][instr[OUTPUT][SYM_NAME]]
                        instr[OUTPUT][LIVE], instr[OUTPUT][NEXT_USE] = entry[LIVE], entry[NEXT_USE]
                        entry[LIVE], entry[NEXT_USE] = False, None

                for instr_in in instr[INPUTS]:
                    if instr_in[SYM_NAME] not in blck[SYM_TABLE]:
                        blck[SYM_TABLE][instr_in[SYM_NAME]] = {LIVE: True, NEXT_USE: instr[ORIG_POS]}
                        if instr_in[SYM_NAME] in blck[OUT_OPERANDS]:
                            instr_in[NEXT_USE], instr_in[LIVE] = blck[OUT_OPERANDS][instr_in[SYM_NAME]], True
                    else:
                        entry = blck[SYM_TABLE][instr_in[SYM_NAME]]
                        instr_in[LIVE], instr_in[NEXT_USE] = entry[LIVE], entry[NEXT_USE]
                        entry[LIVE], entry[NEXT_USE] = True, instr[ORIG_POS]

        # remove dependencies for instructions using operands from B0 (START) block, e.g., stack pointer, ctx
        for out in self.blocks[0][OUT_OPERANDS]:
            target_instr = self.blocks[0][OUT_OPERANDS][out]
            target_block = self.schedule[target_instr][BLOCK]

            for instr in self.blocks[target_block][INSTRUCTIONS]:
                if instr[ORIG_POS] == target_instr:
                    instr[PENDING_DEPS] -= 1

    @staticmethod
    def __diff_dicts(a, b):
        # This method returns a set a - b (elements are copied not referenced), a & b dicts

        a_copy, b_copy = a, b
        return {k: a_copy[k] for k in set(set(a_copy.keys()) - set(b_copy.keys()))}

    @staticmethod
    def __light_copy(a):
        # This method returns a copy of a, a dict

        res = {}
        for k in a.keys():
            res[k] = a[k]

        return res

    def __union_dicts(self, dict1, dict2):
        # This method returns a set a U b (elements are copied not referenced), a & b dicts

        res = self.__light_copy(dict1)

        for elem in dict2:
            if elem not in res or res[elem] > dict2[elem]:
                res[elem] = dict2[elem]

        return res

    def __local_optimizations(self):
        # This method applies to each block mov-alu and movi-exit compression

        for blck in self.blocks:
            self.compress_mov_alu(blck)

        for b in list(self.flow_graph.predecessors(len(self.flow_graph) - 1)):
            self.compress_movi_exit(self.blocks[b])

    @staticmethod
    def is_in_inputs(inputs, output):
        # This method returns True if the output operand is in the input operands set

        for inp in inputs:
            if output == inp[SYM_NAME]:
                return True
        return False

    def compress_mov_alu(self, blck):
        # This method compresses sequences of mov-alu in a single 3 operands instruction. This optimization undo
        # the mov-alu LLVM expansion of 3 operands ALU instructions, since are not supported by x86
        # (but they are in Sephirot)

        for curr in range(1, len(blck[INSTRUCTIONS])):
            curri = blck[INSTRUCTIONS][curr]
            previ = blck[INSTRUCTIONS][curr - 1]

            if is_alu(unpack_instruction(curri[INSTR_B])) and is_mov(unpack_instruction(previ[INSTR_B])) \
                    and (previ[OUTPUT][SYM_NAME] == curri[OUTPUT][SYM_NAME]) \
                    and self.is_in_inputs(curri[INPUTS], curri[OUTPUT][SYM_NAME]) \
                    and is_optimizable_mov_alu(unpack_instruction(curri[INSTR_B])):
                self.program_bin[curri[ORIG_POS]] = modify_register(curri[INSTR_B], previ[INPUTS][0][SYM_NAME],
                                                                    SRC_SHIFT_MOD)
                self.program_bin[curri[ORIG_POS]] = set_opcode(self.program_bin[curri[ORIG_POS]],
                                                               get_correspondent(
                                                                   unpack_instruction(
                                                                       self.program_bin[curri[ORIG_POS]])["opcode"]))
                self.program_str[curri[ORIG_POS]] = self.generate_mov_alu_str(blck[INSTRUCTIONS][curr][INSTR_S],
                                                                              previ[INPUTS][0][SYM_NAME])
                self.program_bin[curri[ORIG_POS] - 1] = NOP
                self.program_str[curri[ORIG_POS] - 1] = "NOP"

                self.mov_alu_compressed += 1  # update statistic of removed instructions

    def compress_movi_exit(self, blck):
        # This method compresses sequences of movi-exit in a single instruction. This optimization leverages the
        # early exit instruction supported by Sephirot

        for curr in range(1, len(blck[INSTRUCTIONS])):
            curri = blck[INSTRUCTIONS][curr]
            previ = blck[INSTRUCTIONS][curr - 1]
            if is_exit(unpack_instruction(curri[INSTR_B])) and is_mov_imm(unpack_instruction(previ[INSTR_B])):
                self.program_bin[curri[ORIG_POS] - 1] = modify_register(previ[INSTR_B], 0, SRC_SHIFT_MOD)
                self.program_bin[curri[ORIG_POS] - 1] = set_opcode(self.program_bin[curri[ORIG_POS] - 1], MOV_EXIT)
                self.program_str[curri[ORIG_POS] - 1] = "exit " + str(unpack_instruction(previ[INSTR_B])["immediate"])

                self.program_bin[curri[ORIG_POS]] = NOP
                self.program_str[curri[ORIG_POS]] = "NOP"

                self.movi_exit_compressed += 1  # update statistic of removed instructions

    @staticmethod
    def generate_mov_alu_str(string, inp):
        # Generate mov-alu instruction string representation, starting from original ALU instruction string

        outreg = re.search("(r)[0-9]+", string).regs[0]
        opcode = re.search("([+^|&-]|[<>]{2})", string).regs[0]
        immediate = re.search("[^r][0-9]+", string).regs[0]

        imm = string[immediate[0]:immediate[1]]
        if imm[0] == "-":
            imm = "(" + imm + ")"

        return string[outreg[0]:outreg[1]] + " = r" + str(inp) + " " + string[opcode[0]:opcode[1]] + " " + imm

    @staticmethod
    def modify_reg_str(instr_str, old_reg, new_reg, only_in=False, only_out=False):
        # Modify register(s) in a instruction string. Can replace only input, only output or both

        splitted = instr_str.split("= ")

        if only_in:
            if "if" in instr_str:
                return instr_str.replace("r" + str(old_reg), "r" + str(new_reg))
            return splitted[0] + "= " + splitted[1].replace("r" + str(old_reg), "r" + str(new_reg))

        elif only_out:
            return splitted[0].replace("r" + str(old_reg), "r" + str(new_reg)) + "= " + splitted[1]

        return instr_str.replace("r" + str(old_reg), "r" + str(new_reg))

    def __local_schedule(self, b, last_t, last_i):
        # This function list schedule the instructions inside a single block, considering input dependencies
        # and output interference. last_t contains the last row used in the resource table,
        # while last_i represents the last scheduled instruction id.

        blck = self.blocks[b]

        # building dependency graph
        data_dep_g = self.__compute_local_dependency_graph(blck)

        # DEBUG: draw block DDG
        if self.debug_draw_ddg:
            p = nx.drawing.nx_pydot.to_pydot(data_dep_g)
            p.write_png(self.filename + '_B' + str(b) + '.png' if self.filename is not None else 'B' + str(b) + '.png')

        # finding local scheduling
        nodes = []
        branch = None

        # toposort dependency graph
        for n in list(filter(lambda x: x >= 0, nx.lexicographical_topological_sort(data_dep_g))):
            if n < len(blck[INSTRUCTIONS]) and blck[INSTRUCTIONS][n] is not None and not is_nop(
                    unpack_instruction(blck[INSTRUCTIONS][n][INSTR_B])):
                if is_branch(unpack_instruction(blck[INSTRUCTIONS][n][INSTR_B])):
                    branch = n
                else:
                    nodes.append(n)
        if branch is not None:
            nodes.append(branch)

        # schedule the instructions following the prioritized topological ordering of the instructions
        max_row, max_inst = last_t, last_i
        for n in nodes:
            # 1. find first row solving input dependencies
            lane, row = self.find_avail_row_lane_input_deps(b, data_dep_g, last_t, max_row, n)

            # 2. find first row solving output interference (if has output)
            inst = blck[INSTRUCTIONS][n]
            if inst[OUTPUT] is not None and inst[OUTPUT][NEXT_USE]:
                orig_lu = self.__find_liveness(inst[OUTPUT][NEXT_USE], inst[OUTPUT][SYM_NAME])
                row_lu = self.schedule[orig_lu][TIME] if self.schedule[orig_lu][LANE] is not None else None

                conflicting = self.reg_cache.get_conflicting(inst[OUTPUT][SYM_NAME], row)

                if conflicting is not None and conflicting[REG] == inst[OUTPUT][SYM_NAME] and \
                        inst[ORIG_POS] != conflicting[ORG_LIVE] and \
                        conflicting[REG] != self.bound_check_cache["pkt_act_reg"]:

                    # excludes subseuquent updates on global registers (used by many blocks)
                    if not self.__conf_starts_before_blck(blck, conflicting) and \
                            not self.__conf_ends_after_blck(blck, conflicting):
                        # try to rename output register
                        old_reg = inst[OUTPUT][SYM_NAME]
                        unav = set(self.reg_cache.get_unavailable(row))
                        try:
                            deps = [n]
                            deps.extend(list(filter(lambda x: x != len(blck[INSTRUCTIONS]) - 1,
                                        list(list(data_dep_g.successors(n))))))
                            self.__rename_registers(deps, blck, unav)
                            self.reg_cache.ch_reg_name(old_reg, inst[OUTPUT][SYM_NAME], inst[ORIG_POS], row)
                        except:
                            # no register available, delaying instruction
                            print(inst[INSTR_S])
                            assert conflicting[ROW_LIVE] is not None, "Unexpected out of block conflict, this may be " \
                                                                      "a bug "
                            lane, row = self.find_avail_row_lane_input_deps(b, data_dep_g,
                                                                            conflicting[ROW_LIVE], max_row, n)
                # update used register cache (wr update)
                self.reg_cache.put_reg_wr(inst[OUTPUT][SYM_NAME], inst[ORIG_POS], orig_lu, row, row_lu)

            # update used register cache (rd update)
            inst_impts = [inp[SYM_NAME] for inp in inst[INPUTS]]
            self.reg_cache.put_reg_rd(inst_impts, row, inst[ORIG_POS])

            # actual scheduling
            self.schedule[blck[INSTRUCTIONS][n][ORIG_POS]][TIME] = row
            self.schedule[blck[INSTRUCTIONS][n][ORIG_POS]][LANE] = lane
            self.resource_table[row][lane] = blck[INSTRUCTIONS][n]

            max_inst = max(max_inst, blck[INSTRUCTIONS][n][ORIG_POS])
            max_row = max(max_row, row)

        return max_row if max_row > last_t else max_row + 1, max_inst, data_dep_g

    def find_avail_row_lane_input_deps(self, b, data_dep_g, last_t, max_row, n):
        # This method find an available (row, lane) for the instruction with local id n, satisfying its input
        # dependencies on the Sephirot architecture

        pred = -1
        row = last_t
        blck = self.blocks[b]

        # find instruction predecessor p and where it was scheduled (row, lane)
        for p in data_dep_g.predecessors(n):
            # predecessor scheduled in previuous blocks
            if p == -1:
                pred = self.__find_definition(blck[INSTRUCTIONS][n][INPUTS], b)
                row = last_t
            # predecessor scheduled later in this block
            elif self.schedule[blck[INSTRUCTIONS][p][ORIG_POS]][TIME] >= row:
                row = self.schedule[blck[INSTRUCTIONS][p][ORIG_POS]][TIME] \
                      + (1 if self.schedule[blck[INSTRUCTIONS][p][ORIG_POS]][TIME] == row else 0)
                pred = blck[INSTRUCTIONS][p][ORIG_POS]

        # if the instruction is a branch must be on the last row of the block
        if is_branch(unpack_instruction(blck[INSTRUCTIONS][n][INSTR_B])):
            row = max(row, max_row - 1)

        row += 1  # delay = 1 clock cycle (at least 1 clock cycle from its predecessor)

        # find first clock cycle available (non full row)
        while sum(x is not None for x in self.resource_table[row]) == NUM_LANES:
            row += 1

        # branches can only live on lane 0 (if BRANCH_ALL_LANES is disabled)
        if not BRANCH_ALL_LANES and is_branch(unpack_instruction(blck[INSTRUCTIONS][n][INSTR_B])):
            if row > 0 and pred is not None and row == self.schedule[pred][TIME] + 1 \
                    and self.schedule[pred][BLOCK] <= b and self.schedule[pred][LANE] != 0:
                row += 1
            while self.resource_table[row][0] is not None:
                row += 1
            lane = 0

        # DATA-HAZARD: back to back depending instructions must be on the same lane!
        elif row > 0 and pred is not None and row == self.schedule[pred][TIME] + 1 and self.schedule[pred][
            BLOCK] <= b:
            lane = self.schedule[pred][LANE]
            while self.resource_table[row][lane] is not None:  # if enters no more back to back
                row += 1
                for lane in range(NUM_LANES):
                    if self.resource_table[row][lane] is None:
                        break

        else:  # first available (no hw constraint applicable)
            lane = 0
            found = False
            while self.resource_table[row][lane] is not None:
                for lane in range(NUM_LANES):
                    if self.resource_table[row][lane] is None:
                        found = True
                        break
                if not found:
                    row += 1
        return lane, row

    def __compute_local_dependency_graph(self, blck):
        # This method computes the DDG for the instructions inside the block blck

        data_dep_g = nx.DiGraph()
        edges = []

        data_dep_g.add_node(-1, shape="circle", style="filled", fillcolor="black")
        for reg in blck[IN_OPERANDS]:
            for i in range(len(blck[INSTRUCTIONS])):
                if self.is_in_inputs(blck[INSTRUCTIONS][i][INPUTS], reg):
                    edges.append((-1, i))
                if blck[INSTRUCTIONS][i][OUTPUT] is not None and blck[INSTRUCTIONS][i][OUTPUT][SYM_NAME] == reg:
                    break

        data_dep_g.add_node(len(blck[INSTRUCTIONS]), shape="circle", style="filled", fillcolor="black")
        for reg in blck[OUT_OPERANDS]:
            for i in range(len(blck[INSTRUCTIONS]) - 1, -1, -1):
                if blck[INSTRUCTIONS][i][OUTPUT] is not None and blck[INSTRUCTIONS][i][OUTPUT][SYM_NAME] == reg:
                    edges.append((i, len(blck[INSTRUCTIONS])))
                    break
        if is_branch(unpack_instruction(blck[INSTRUCTIONS][-1][INSTR_B])):
            edges.append((len(blck[INSTRUCTIONS]) - 1, len(blck[INSTRUCTIONS])))

        for i in range(len(blck[INSTRUCTIONS])):
            if not is_nop(unpack_instruction(blck[INSTRUCTIONS][i][INSTR_B])):
                data_dep_g.add_node(i, shape="square", label=blck[INSTRUCTIONS][i][INSTR_S])
            else:
                data_dep_g.add_node(i, shape="square", label="NOP")

            if blck[INSTRUCTIONS][i][OUTPUT] is not None:
                reg = blck[INSTRUCTIONS][i][OUTPUT][SYM_NAME]
                for j in range(i + 1, len(blck[INSTRUCTIONS])):
                    if self.is_in_inputs(blck[INSTRUCTIONS][j][INPUTS], reg):
                        edges.append((i, j))
                    if blck[INSTRUCTIONS][j][OUTPUT] is not None and blck[INSTRUCTIONS][j][OUTPUT][SYM_NAME] == reg:
                        break

        data_dep_g.add_edges_from(edges)

        return data_dep_g

    def __print_resource_table(self):
        # This method prints the resource table showing the allocated instructions in their string representation

        tab = []
        for row in self.resource_table:
            tab.append([lane[INSTR_S] if lane is not None else "NOP" for lane in row])
        TableIt.printTable(tab)

    def __global_schedule(self):
        # This method schedules each block using __local_schedule

        blocks = list(filter(lambda x: self.blocks[x][TYPE] == BlockType.BASIC,
                             list(nx.lexicographical_topological_sort(self.flow_graph))))

        last_t = -1  # last used row in resource table
        last_i = -1  # last scheduled instruction (global id)
        for b in blocks:
            initial_t = last_t + 1
            blck = self.blocks[b]

            last_t, last_i, ddg = self.__local_schedule(b, last_t, last_i)  # schedule block
            self.reg_cache.change_block(blck[START] + blck[LEN])

        self.resource_table = self.resource_table[:last_t + 1]

        if self.debug_print_resource_table:
            self.__print_resource_table()

    def global_to_local(self, blck, index):
        # This method resolves from global instruction index to local block index

        for i in range(len(blck[INSTRUCTIONS])):
            if blck[INSTRUCTIONS][i][ORIG_POS] == index:
                return i
        print("\033[91mInstruction with index " + str(index) + " not found in block B" + str(self.blocks.index(blck)))
        exit(-1)

    def __compute_dominators(self, flow_graph):
        # This method compute dominators nodes (for each node) of the flow_graph

        dominators = [{b for b in range(len(self.blocks))} for b in range(len(self.blocks))]

        reverse_postorder = list(nx.lexicographical_topological_sort(flow_graph))
        dominators[reverse_postorder[0]] = {reverse_postorder[0]}
        changed = True
        while changed:
            changed = False
            for b in reverse_postorder[1:-1]:
                all_dom_preds = [dominators[p] for p in flow_graph.predecessors(b)]
                if len(all_dom_preds) == 0:
                    return set()
                new_set = set.intersection(*all_dom_preds).union({b})

                if new_set != dominators[b]:
                    dominators[b] = new_set
                    changed = True

        return dominators

    def __find_definition(self, inputs, start_block):
        # This method forward scans starting from start_block, finding the first instruction defining one of the
        # input operands in inputs. Returns the instruction global id

        for b in range(start_block - 1, 0, -1):
            for inp in inputs:
                if inp[SYM_NAME] in self.blocks[b][DEFS] and self.blocks[b][TYPE] == BlockType.BASIC:
                    for instr in reversed(self.blocks[b][INSTRUCTIONS]):
                        if instr[OUTPUT] is not None and instr[OUTPUT][SYM_NAME] == inp[SYM_NAME]:
                            return instr[ORIG_POS]
        return None

    @staticmethod
    def __call_to_regs(call_id):
        # This method returns for each helper function call its number of arguments (r1-r5)

        CALLS_TO_REG = {1: 4, 5: 0, 6: 5, 8: 0, 23: 2, 25: 3, 28: 4, 44: 2, 51: 3, 54: 2, 65: 2, 69: 4}

        if call_id not in CALLS_TO_REG:
            n_args = 5
        else:
            n_args = CALLS_TO_REG[call_id]
        return [i for i in range(1, n_args + 1)]

    def __fix_branch_offsets(self):
        # This method fixes the offset of branches after the scheduling

        for r in range(len(self.resource_table)):
            row = self.resource_table[r]
            if row[0] is not None and is_jump(unpack_instruction(row[0][INSTR_B])):
                target_b = row[0][JMP_BLOCK]

                leader = self.blocks[target_b][INSTRUCTIONS][0][ORIG_POS]
                for i in self.blocks[target_b][INSTRUCTIONS]:
                    if i is not None and i[INSTR_S] != "NOP":
                        leader = i[ORIG_POS]

                old_offset = unpack_instruction(row[0][INSTR_B])[OFFSET]
                row[0][INSTR_B] = modify_offset(row[0][INSTR_B], self.schedule[leader][TIME] - r - 1)

                row[0][INSTR_S] = row[0][INSTR_S].replace(str(old_offset), str(self.schedule[leader][TIME] - r - 1))

    def __remove_memory_boundaries_checks(self):
        # This method accelerates the program removing the instructions performing memory boundary checks

        # searching exit block
        end_block = list(nx.lexicographical_topological_sort(self.flow_graph))[-1]
        assert self.blocks[end_block][TYPE] == BlockType.EXIT and len(list(self.flow_graph.predecessors(
            end_block))) == 1, "Ending block must be a BlockType.EXIT, with one father, seems a bug..."

        exit_block = list(self.flow_graph.predecessors(end_block))[0]

        tbrmvd = dict()  # instructions candidate to be removed
        offsets = set()  # offsets to be checked

        # searching packet action register or a default packet action
        blck = self.blocks[exit_block]
        assert (blck[INSTRUCTIONS][-1] is not None and is_exit(unpack_instruction(blck[INSTRUCTIONS][-1][INSTR_B]))) \
               or (blck[INSTRUCTIONS][-2] is not None and is_exit(unpack_instruction(blck[INSTRUCTIONS][-2][INSTR_B]))), \
            "Last block must contain an [mov]exit, seems a bug..."
        if len(blck[INSTRUCTIONS]) >= 2:
            if is_mov_exit(
                    unpack_instruction(blck[INSTRUCTIONS][-2][INSTR_B])):  # programs ends with mov-exit: default action
                self.bound_check_cache["pkt_act"] = unpack_instruction(blck[INSTRUCTIONS][-1][INSTR_B])["immediate"]
            else:  # program ends with r0 = pkt_act_reg, exit
                for inst in reversed(blck[INSTRUCTIONS][-2:]):
                    unpkd = unpack_instruction(inst[INSTR_B])
                    if is_mov(unpkd) and get_output(unpkd) == 0:  # searching r0 = rx
                        self.bound_check_cache["pkt_act_reg"] = get_inputs(unpkd)[0]
                        break
        else:
            self.bound_check_cache["pkt_act_reg"] = 0

        blocks = list(nx.lexicographical_topological_sort(self.flow_graph))
        assert self.blocks[blocks[0]][TYPE] == BlockType.START and len(
            list(self.flow_graph.successors(blocks[0]))) == 1, \
            "Starting block must be a BlockType.START, with one successor, seems a bug..."

        # searching ctx register definition
        blck = self.blocks[1]  # if renamed it is done in first block
        for inst in blck[INSTRUCTIONS]:
            unpkd = unpack_instruction(inst[INSTR_B])
            if is_mov(unpkd) and inst[INPUTS][0][SYM_NAME] == 1:  # ctx is passed to the eBPF program with r1
                next = self.__find_liveness(inst[OUTPUT][NEXT_USE], inst[OUTPUT][SYM_NAME])
                if next is not None:
                    self.bound_check_cache["ctx"] = (inst[OUTPUT][SYM_NAME], next)
                    tbrmvd[inst[ORIG_POS]] = (NOP, "NOP")
                    break
        if self.bound_check_cache["ctx"][0] is None:  # if not defined is the default r1
            if 1 not in blck[IN_OPERANDS]:
                return None  # no accesses to ctx
            next = self.__find_liveness(blck[IN_OPERANDS][1], 1)
            if next is not None:
                self.bound_check_cache["ctx"] = (1, next)

        for b in list(nx.lexicographical_topological_sort(self.flow_graph))[1:-1]:
            blck = self.blocks[b]
            if blck[TYPE] != BlockType.BASIC:
                continue

            # memory boundary check
            # verifying assumption: if rx > ry goto EXIT block
            local_if_idx = len(blck[INSTRUCTIONS]) - 1
            if not is_if_greater_eq(unpack_instruction(blck[INSTRUCTIONS][-1][INSTR_B])) or exit_block not in blck[
                TNEXT]:
                continue
            ry, rx = get_inputs(unpack_instruction(blck[INSTRUCTIONS][-1][INSTR_B]))

            # building dependency graph
            data_dep_g = self.__compute_local_dependency_graph(blck)

            # verifying assumption: ry is the packet length ctx->data_end
            # not (is in cache && is valid)
            if not (self.bound_check_cache["ctx_data_end"][0] == ry and self.bound_check_cache["ctx_data_end"][
                1] >= blck[INSTRUCTIONS][local_if_idx][ORIG_POS]):
                inst = self.__is_data_len(ry, local_if_idx, data_dep_g, b)
                if not (inst is not None and
                        blck[INSTRUCTIONS][inst][INPUTS][0][SYM_NAME] == self.bound_check_cache["ctx"][0] and
                        blck[INSTRUCTIONS][inst][ORIG_POS] <= self.bound_check_cache["ctx"][1]):
                    continue
                tbrmvd[blck[INSTRUCTIONS][inst][ORIG_POS]] = (NOP, "NOP")

                # update cache for ctx->data_len
                next = self.__find_liveness(blck[INSTRUCTIONS][-1][INPUTS][0][NEXT_USE], ry)
                if next is not None:
                    self.bound_check_cache["ctx_data_end"] = (ry, next)

            # verifying assumption: rx is an address in the packet, ctx->data + OFFSET
            # not (is in cache && is valid)
            if not (rx == self.bound_check_cache["ctx_data_+_offset"][0] and
                    self.bound_check_cache["ctx_data_+_offset"][1] >= blck[INSTRUCTIONS][local_if_idx][ORIG_POS]):
                offset, tbr = self.__is_packet_offset(rx, local_if_idx, data_dep_g, b)
                if offset is None:
                    continue
                if blck[INSTRUCTIONS][local_if_idx][INPUTS][1][NEXT_USE] is not None:
                    next = self.__find_liveness(blck[INSTRUCTIONS][local_if_idx][INPUTS][1][NEXT_USE], rx)
                    if next is not None:
                        self.bound_check_cache["ctx_data_+_offset"] = (rx, next, offset)

                for k in tbr:
                    tbrmvd[k] = (NOP, "NOP")
                offsets.add(offset)
            else:
                offsets.add(self.bound_check_cache["ctx_data_+_offset"][2])

            # remove 'if rx > ry'
            tbrmvd[blck[INSTRUCTIONS][local_if_idx][ORIG_POS]] = (NOP, "NOP")

            # remove setting pkt_act_reg = DROP
            if self.bound_check_cache["pkt_act"] is None:  # default action not set
                for inst in blck[INSTRUCTIONS]:
                    unpkd = unpack_instruction(inst[INSTR_B])
                    if is_mov_imm(unpkd) and inst[OUTPUT][SYM_NAME] == self.bound_check_cache["pkt_act_reg"] and \
                            unpkd["immediate"] == XDPAction.DROP:
                        tbrmvd[inst[ORIG_POS]] = (NOP, "NOP")

        self.__remove_independents(tbrmvd)

        return offsets

    def __is_packet_offset(self, rx, inst_idx, data_dep_g, b_idx):
        # This method checks if in register is contained the computation of a packet offset

        preds = list(data_dep_g.predecessors(inst_idx))
        blck = self.blocks[b_idx]

        tbrmvd = set()

        for p in preds:
            if p >= 0 and blck[INSTRUCTIONS][p][OUTPUT][SYM_NAME] == rx:
                unpkd = unpack_instruction(blck[INSTRUCTIONS][p][INSTR_B])

                # searching a sequence ALU_ADD(MEM(r1 + 0), offset)
                if is_alu_add_imm(unpkd):
                    offset = unpkd["immediate"]
                    tbrmvd.add(blck[INSTRUCTIONS][p][ORIG_POS])

                    # MEM(r1 + 0) in cache && valid
                    if blck[INSTRUCTIONS][p][INPUTS][0][SYM_NAME] == self.bound_check_cache["ctx_data"][0] and \
                            blck[INSTRUCTIONS][p][ORIG_POS] <= self.bound_check_cache["ctx_data"][1]:
                        return offset, tbrmvd
                    else:
                        # searching MEM(r1 + 0)
                        pred = list(data_dep_g.predecessors(p))[0]
                        if self.__is_mem_load(blck[INSTRUCTIONS][pred][INSTR_B], 32, 0) and \
                                blck[INSTRUCTIONS][pred][INPUTS][0][SYM_NAME] == self.bound_check_cache["ctx"][0] and \
                                blck[INSTRUCTIONS][pred][ORIG_POS] <= self.bound_check_cache["ctx"][1]:
                            tbrmvd.add(blck[INSTRUCTIONS][pred][ORIG_POS])

                            # update cache for ctx->data
                            next = self.__find_liveness(blck[INSTRUCTIONS][p][INPUTS][0][NEXT_USE],
                                                        blck[INSTRUCTIONS][pred][OUTPUT][SYM_NAME])
                            if next is not None:
                                self.bound_check_cache["ctx_data"] = (blck[INSTRUCTIONS][pred][OUTPUT][SYM_NAME], next)

                            return offset, tbrmvd

        return None, None

    def __is_data_len(self, ry, inst_idx, data_dep_g, b_idx):
        # This method checks if the register contains the data_len value

        preds = list(data_dep_g.predecessors(inst_idx))
        blck = self.blocks[b_idx]

        for p in preds:
            if p >= 0 and blck[INSTRUCTIONS][p][OUTPUT][SYM_NAME] == ry:
                if self.__is_mem_load(blck[INSTRUCTIONS][p][INSTR_B], 32, 4):
                    return p
        return None

    def __find_liveness(self, next, reg):
        # This method returns the last instruction using a given value

        n_next = next
        while n_next is not None:
            t_block = self.blocks[self.schedule[n_next][BLOCK]]
            t_inst = t_block[INSTRUCTIONS][self.global_to_local(t_block, n_next)]

            if t_inst[OUTPUT] is not None and t_inst[OUTPUT][SYM_NAME] == reg or is_call(
                    unpack_instruction(t_inst[INSTR_B])):
                return t_inst[ORIG_POS]

            for inp in t_inst[INPUTS]:
                if inp[SYM_NAME] == reg:
                    if inp[NEXT_USE] is None:
                        return n_next
                    n_next = inp[NEXT_USE]

    def __is_mem_load(self, instruct, size, offset):
        # This method checks if an instruction is a load from memory suitable to be promoted to a 48 bit read

        unpkd = unpack_instruction(instruct)

        return load_to_size(unpkd) is not None and load_to_size(unpkd) == size and unpkd[OFFSET] == offset

    def __remove_independents(self, tbrmvd):
        # This method removes instructions in tbrmvd and instructions depending on them

        for orig_pos in reversed(sorted(list(tbrmvd.keys()))):
            if self.program_bin[orig_pos] is None or self.program_bin[orig_pos] == 0:
                continue
            elif is_branch(unpack_instruction(self.program_bin[orig_pos])):
                self.program_bin[orig_pos] = tbrmvd[orig_pos][0]
                self.program_str[orig_pos] = tbrmvd[orig_pos][1]
            else:
                t_block = self.blocks[self.schedule[orig_pos][BLOCK]]
                t_inst = t_block[INSTRUCTIONS][self.global_to_local(t_block, orig_pos)]

                self.program_bin[orig_pos] = tbrmvd[orig_pos][0]
                self.program_str[orig_pos] = tbrmvd[orig_pos][1]

                # eliminating depending instructions
                if t_inst[OUTPUT] is not None and tbrmvd[orig_pos][1] == "NOP":
                    next = t_inst[OUTPUT][NEXT_USE]
                    out_reg = t_inst[OUTPUT][SYM_NAME]

                    pending = [orig_pos]
                    while next is not None:
                        t_block = self.blocks[self.schedule[next][BLOCK]]
                        t_inst = t_block[INSTRUCTIONS][self.global_to_local(t_block, next)]

                        if t_inst[ORIG_POS] not in tbrmvd:
                            break

                        for inp in t_inst[INPUTS]:
                            if inp[SYM_NAME] == out_reg:
                                pending.append(next)
                                next = inp[NEXT_USE]
                                if next is None:
                                    for i in pending:
                                        self.program_bin[i] = NOP
                                        self.program_str[i] = "NOP"

                        if t_inst[OUTPUT] is not None and t_inst[OUTPUT][SYM_NAME] == out_reg or is_call(
                                unpack_instruction(t_inst[INSTR_B])):
                            for i in pending:
                                self.program_bin[i] = NOP
                                self.program_str[i] = "NOP"
                            break

    def __advanced_optimizations(self):
        # This method performs some advanced optimizations, such as promoting load/store at 48 bit
        # and eliminating memory zeroing

        optimizations = [LoadStore48(), Load48Store48(), MemsetToZero()]

        for blck in self.blocks:
            if blck[TYPE] != BlockType.BASIC:
                continue
            for instr in blck[INSTRUCTIONS]:
                if instr is not None:
                    for opt in optimizations:
                        opt.parse_instruction(instr[INSTR_B], instr[ORIG_POS])

        res = dict()
        for opt in optimizations:
            for r in opt.get_optimized_instructions():
                res.update(r)

        self.__remove_independents(res)

    def __move_branches(self, b, last_t):
        # This method moves a branch from a single instruction block following the current block, when they
        # represents different switch cases

        blck = self.blocks[b]

        unpkd = unpack_instruction(blck[INSTRUCTIONS][-1][INSTR_B])
        if not is_if_branch(unpkd):
            return
        inputs = set(get_inputs(unpkd))

        avail = sum(i is None or i[INSTR_B] == NOP for i in self.resource_table[last_t])
        found = True
        curr_b = blck[FNEXT]
        while curr_b is not None and avail > 0 and found == True:
            found = False

            cand_blck = self.blocks[curr_b]
            if len(cand_blck[INSTRUCTIONS]) == 1:
                unpkd = unpack_instruction(cand_blck[INSTRUCTIONS][0][INSTR_B])

                if is_if_branch(unpkd) and len(inputs.difference(set(get_inputs(unpkd)))) == 0:
                    for lane in range(NUM_LANES):
                        if self.resource_table[last_t][lane] is None:
                            self.resource_table[last_t][lane] = cand_blck[INSTRUCTIONS][0]

                            self.schedule[cand_blck[INSTRUCTIONS][0][ORIG_POS]][TIME] = last_t
                            self.schedule[cand_blck[INSTRUCTIONS][0][ORIG_POS]][LANE] = lane
                            self.schedule[cand_blck[INSTRUCTIONS][0][ORIG_POS]][BLOCK] = b

                            cand_blck[INSTRUCTIONS][0] = {INSTR_B: NOP,
                                                          INSTR_S: "NOP",
                                                          INPUTS: [],
                                                          OUTPUT: None,
                                                          ORIG_POS: None,
                                                          JMP_BLOCK: None,
                                                          PENDING_DEPS: 0
                                                          }
                            cand_blck[TYPE] = BlockType.DISABLED # block can be eliminated

                            avail -= 1
                            found = True
                            curr_b = cand_blck[FNEXT]
                            break

    def __rename_registers(self, tbmd, blck, used):
        # This method modifies output registers of the instructions in tbmd, choosing a register which is not already
        # used in the current row (list of used regs in used) and it is not used in subsequent blocks (it may be a reg
        # for a helper function call, or simply a reg used later which requires to modify further instructions).
        # Returns the new register used

        assert len(tbmd) != 0, "Call to __rename_register for 0 instructions"

        new_reg = STACK_REG
        for i in range(0, 16):  # valid to use regs in r0-r15
            if i != STACK_REG and i not in blck[OUT_OPERANDS] and i not in used:
                new_reg = i
                break

        # No free reg was found
        if new_reg == STACK_REG:
            raise Exception("No registers available")

        instr = blck[INSTRUCTIONS][tbmd[0]]
        instr_id = instr[ORIG_POS]
        old_reg = instr[OUTPUT][SYM_NAME]

        # instructions in tbmd are ordered (in the dependency chain), first instruction needs to modify only dst
        # register
        instr[INSTR_B] = modify_register(instr[INSTR_B], new_reg, DST_SHIFT_MOD)
        instr[INSTR_S] = self.modify_reg_str(instr[INSTR_S], old_reg, new_reg, only_out=True)
        instr[OUTPUT][SYM_NAME] = new_reg

        # instr was already scheduled
        if self.schedule[instr_id][LANE] is not None:
            rt_inst = self.resource_table[self.schedule[instr_id][TIME]][self.schedule[instr_id][LANE]]
            if rt_inst[ORIG_POS] == instr[ORIG_POS]:
                self.resource_table[self.schedule[instr_id][TIME]][self.schedule[instr_id][LANE]] = instr

        for i in tbmd[1:]:
            instr = blck[INSTRUCTIONS][i]
            instr_id = instr[ORIG_POS]

            # subsequent instructions in tbmd needs to modify only src registers
            for inp in instr[INPUTS]:
                if inp[SYM_NAME] == old_reg:
                    instr[INSTR_S] = self.modify_reg_str(instr[INSTR_S], old_reg, new_reg, only_in=True)
                    instr[INSTR_B] = modify_register(instr[INSTR_B], new_reg, SRC_SHIFT_MOD)
                    inp[SYM_NAME] = new_reg

                    if self.schedule[instr_id][LANE] is not None:
                        rt_inst = self.resource_table[self.schedule[instr_id][TIME]][self.schedule[instr_id][LANE]]
                        if rt_inst[ORIG_POS] == instr[ORIG_POS]:
                            self.resource_table[self.schedule[instr_id][TIME]][self.schedule[instr_id][LANE]] = instr

            # the instruction is a branch, closing the block and therefore the dependency chain tbmd
            if is_branch(unpack_instruction(instr[INSTR_B])):
                break

            # the instruction redefines the output operand, no need to continue in the chain
            if instr[OUTPUT] is not None and instr[OUTPUT][SYM_NAME] == old_reg:
                break

        return new_reg

    @staticmethod
    def __conf_ends_after_blck(blck, conflicting):
        return conflicting[ORG_LIVE] > blck[START] + blck[LEN]

    @staticmethod
    def __conf_starts_before_blck(blck, conflicting):
        return conflicting[ORIG_DEF] < blck[START]
