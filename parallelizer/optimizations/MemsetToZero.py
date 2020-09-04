from ebpf_parser import is_mov_imm, unpack_instruction, get_output, is_store, get_inputs, NOP, is_load, load_to_size
from optimizations.Optimization import *

OFFSET = "offset"
LEN = "len"


class MemsetToZero(Optimization):

    def __init__(self):
        states = ["initial", "movi0", "storing"]

        transitions = [
            {SOURCE: "initial", DESTINATION: "movi0", CONDITIONS: ["is_movi_to_zero"],
             AFTER: ["enter_movi0"]},
            {SOURCE: "initial", DESTINATION: "initial", CONDITIONS: ["is_accessed"],
             AFTER: ["after_accessed"]},
            {SOURCE: "initial", DESTINATION: "initial", UNLESS: ["is_movi_to_zero"]},

            {SOURCE: "movi0", DESTINATION: "storing", CONDITIONS: ["is_store_from_zeroed_reg_to_stack"],
             AFTER: ["enter_store", "after_accessed"]},
            {SOURCE: "movi0", DESTINATION: "initial", CONDITIONS: ["is_write_to_reg"], UNLESS: ["is_movi_to_zero"],
             AFTER: ["reset_register", "delete_last_optimized", "new_optimized_empty_list"]},
            {SOURCE: "movi0", DESTINATION: "initial", CONDITIONS: ["is_accessed"],
             AFTER: ["after_accessed", "reset_register", "delete_last_optimized", "new_optimized_empty_list"]},
            {SOURCE: "movi0", DESTINATION: "movi0", CONDITIONS: ["is_movi_to_zero"],
             AFTER: ["delete_last_optimized", "new_optimized_empty_list", "enter_movi0"]},

            {SOURCE: "storing", DESTINATION: "storing", CONDITIONS: ["is_store_from_zeroed_reg_to_stack"],
             AFTER: ["enter_store", "after_accessed"]},
            {SOURCE: "storing", DESTINATION: "movi0", CONDITIONS: ["is_movi_to_zero"],
             AFTER: ["new_optimized_empty_list", "enter_movi0"]},
            {SOURCE: "storing", DESTINATION: "initial", UNLESS: ["is_store_from_zeroed_reg_to_stack"],
             AFTER: ["reset_register", "new_optimized_empty_list", "after_accessed"]},
            {SOURCE: "storing", DESTINATION: "initial", UNLESS: ["is_accessed"],
             AFTER: ["after_accessed", "reset_register", "new_optimized_empty_list"]},
        ]

        for t in transitions:
            t[TRIGGER] = DEFAULT_TRIGGER

        self.__machine = Machine(model=self, states=states, transitions=transitions, initial=states[0])

        self.register = None
        self.accessed_data = set()
        super(MemsetToZero, self).__init__()

    def is_movi_to_zero(self):
        unpkd = unpack_instruction(self.instruction)
        if is_mov_imm(unpkd) and unpkd["immediate"] == 0:
            return True
        else:
            return False

    def is_store_from_zeroed_reg_to_stack(self):
        unpkd = unpack_instruction(self.instruction)
        return is_store(unpkd) and unpkd["offset"] not in self.accessed_data and get_inputs(unpkd)[
            0] == self.register and get_inputs(unpkd)[1] == 10  # r10 contains stack

    def is_write_to_reg(self):
        out = get_output(unpack_instruction(self.instruction))
        return out is not None and out == self.register

    def is_accessed(self):
        unpkd = unpack_instruction(self.instruction)
        return (is_load(unpkd) and get_output(unpkd) == 10) or \
               (is_store(unpkd) and get_inputs(unpkd)[1] == 10)  # r10 contains stack

    def after_accessed(self):
        self.accessed_data.add(unpack_instruction(self.instruction)["offset"])

    def enter_movi0(self):
        unpkd = unpack_instruction(self.instruction)
        self.register = get_output(unpkd)
        self.optimized_instructions[-1][self.instruction_id] = (NOP, "NOP")

    def enter_store(self):
        self.optimized_instructions[-1][self.instruction_id] = (NOP, "NOP")

    def reset_register(self):
        self.register = None
