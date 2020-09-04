from ebpf_parser import is_mov_imm, unpack_instruction, get_output, is_store, get_inputs, NOP, is_load, load_to_size, \
    store_to_size, is_a_load48, is_a_store48, print_unpkd, set_opcode, STORE48, LOAD48, modify_offset
from optimizations.Optimization import *

L_L_B = "l_l_b" # left_lower_bound
L_U_B = "l_u_b"
R_L_B = "r_l_b"
R_U_B = "r_u_b"

PENDING = 0 # first load-store pair
FORWARD = 1 # memcpy copying fwd
BACKWARD = 2 # memcpy copying bcw


class LoadStore48(Optimization):

    def __init__(self):
        states = ["initial", "load", "loadstore"]

        transitions = [
            {SOURCE: "initial", DESTINATION: "load", CONDITIONS: ["is_a_load"],
             AFTER: ["after_load"]},

            {SOURCE: "load", DESTINATION: "loadstore", CONDITIONS: ["is_a_store", "is_contiguous_store"],
             AFTER: ["after_store"]},
            {SOURCE: "load", DESTINATION: "initial", UNLESS: ["is_contiguous_store", "is_a_load"],
             AFTER: ["delete_last_optimized", "new_optimized_empty_list", "reset_state"]},
            {SOURCE: "load", DESTINATION: "load", CONDITIONS: ["is_a_load"],
             AFTER: ["delete_last_optimized", "new_optimized_empty_list", "reset_state", "after_load"]},

            {SOURCE: "loadstore", DESTINATION: "load", CONDITIONS: ["is_a_load", "is_contiguous_load"],
             UNLESS: ["is_completed"],
             AFTER: ["after_load"]},
            {SOURCE: "loadstore", DESTINATION: "load", CONDITIONS: ["is_a_load"],
             UNLESS: ["is_completed"],
             AFTER: ["delete_last_optimized", "new_optimized_empty_list", "reset_state", "after_load"]},
            {SOURCE: "loadstore", DESTINATION: "load", CONDITIONS: ["is_a_load", "is_completed"],
             UNLESS: ["is_contiguous_load"],
             AFTER: ["finalize_optimized_intructions", "new_optimized_empty_list", "reset_state", "after_load"]},
            {SOURCE: "loadstore", DESTINATION: "initial", CONDITIONS: ["is_completed"], UNLESS: ["is_a_load"],
             AFTER: ["finalize_optimized_intructions", "new_optimized_empty_list", "reset_state"]},
            {SOURCE: "loadstore", DESTINATION: "initial", UNLESS: ["is_completed"],
             AFTER: ["delete_last_optimized", "new_optimized_empty_list", "reset_state"]}
        ]

        for t in transitions:
            t[TRIGGER] = DEFAULT_TRIGGER

        self.__machine = Machine(model=self, states=states, transitions=transitions, initial=states[0])

        self.load = {L_L_B: None, L_U_B: None, R_L_B: None, R_U_B: None}
        self.store = {L_L_B: None, L_U_B: None, R_L_B: None, R_U_B: None}
        self.direction = None
        self.n = 0
        self.size = None
        super(LoadStore48, self).__init__()


    def is_a_load(self):
        return is_a_load48(unpack_instruction(self.instruction))

    def is_a_store(self):
        return is_a_store48(unpack_instruction(self.instruction))

    def is_contiguous_load(self):
        unpkd = unpack_instruction(self.instruction)
        if not is_load(unpkd):
            return False

        if self.direction is None:
            return True

        offset = unpkd["offset"]
        self.size = int(load_to_size(unpkd) / 8)

        if self.direction == PENDING and (offset + self.size == self.load[L_L_B] or self.load[L_U_B] == offset):
            return True
        elif self.direction == FORWARD and (offset == self.load[L_U_B] or
                                            offset == self.load[R_U_B] or
                                            (not self.is_completed() and
                                             offset == (self.load[R_U_B]-int(6/self.size)))):
            return True
        elif self.direction == BACKWARD and ((offset + self.size) == self.load[L_L_B] or
                                             (offset + self.size) == self.load[R_L_B] or
                                             (not self.is_completed() and
                                              offset + self.size == (self.load[L_U_B] + (int(6/self.size)-self.n)*self.size))):
            return True
        return False

    def is_contiguous_store(self):
        unpkd = unpack_instruction(self.instruction)
        if not is_store(unpkd):
            return False

        offset = unpkd["offset"]
        self.size = int(store_to_size(unpkd) / 8)

        if self.direction == PENDING:
            return True
        elif self.direction == FORWARD and (offset == self.store[R_U_B] or
                                            offset == self.store[L_U_B] or
                                            (not self.is_completed() and
                                             offset == (self.store[R_U_B] - int(6 / self.size)))):
            return True
        elif self.direction == BACKWARD and ((offset + self.size) == self.store[L_L_B] or
                                             (offset + self.size) == self.store[R_L_B] or
                                             (not self.is_completed() and
                                             offset + self.size == (self.store[L_U_B] + (int(6 / self.size) - self.n*self.size)))):
            return True
        return False

    def is_completed(self):
        if self.n != (int(6/self.size)):
            return False
        if self.direction == FORWARD:
            if self.store[L_L_B] is None and self.store[L_U_B] is None:
                return (self.store[R_U_B] - self.store[R_L_B]) == 6
            else:
                return (self.store[R_U_B] - self.store[L_L_B]) == 6 and self.store[L_U_B] == self.store[R_L_B]
        elif self.direction == BACKWARD:
            if self.store[R_L_B] is None and self.store[R_U_B] is None:
                return (self.store[L_U_B] - self.store[L_L_B]) == 6
            else:
                return (self.store[R_U_B] - self.store[L_L_B]) == 6 and self.store[L_U_B] == self.store[R_L_B]
        return False

    def after_load(self):
        unpkd = unpack_instruction(self.instruction)
        if load_to_size(unpkd) is None:
            assert False, ("invalid call of after_load, !illegal transition!")

        offset = unpkd["offset"]
        if self.size is None:
            self.size = int(load_to_size(unpkd) / 8)
        else:
            assert self.size == int(load_to_size(unpkd) / 8)

        if self.direction is None:  # first load-store pair
            self.direction = PENDING
            self.load[L_L_B], self.load[L_U_B] = offset, offset + self.size
        elif self.direction == PENDING:  # second store-store pair
            if self.load[L_L_B] == offset + self.size:  # backward
                self.direction = BACKWARD
                self.load[L_L_B] -= self.size
            elif self.load[L_U_B] == offset:  # forward
                self.direction = FORWARD
                self.load[R_L_B], self.load[R_U_B] = self.load[L_L_B], offset + self.size
                self.load[L_L_B], self.load[L_U_B] = None, None
                
                self.store[R_L_B], self.store[R_U_B] = self.store[L_L_B], offset + self.size
                self.store[L_L_B], self.store[L_U_B] = None, None
            else:
                assert False, ("invalid call of after_load, !illegal transition!")
        elif self.direction == FORWARD:
            if offset == self.load[L_U_B]:
                self.load[L_U_B] += self.size
            elif offset == self.load[R_U_B]:
                self.load[R_U_B] += self.size
            elif offset == (self.load[R_U_B]-int(6/self.size)):
                self.load[L_L_B], self.load[L_U_B] = offset, offset + self.size
            else:
                assert False, ("invalid call of after_load, !illegal transition!")            
        elif self.direction == BACKWARD:
            if (offset + self.size) == self.load[L_L_B]:
                self.load[L_L_B] -= self.size                    
            elif (offset + self.size) == self.load[R_L_B]:
                self.load[R_L_B] -= self.size
            elif (offset + self.size) == (self.load[L_U_B] + (int(6 / self.size) - self.n) * self.size):
                self.load[R_L_B], self.load[R_U_B] = offset, offset + self.size
            else:
                assert False, ("invalid call of after_load, !illegal transition!")

        self.optimized_instructions[-1][self.instruction_id] = (self.instruction, "NOP")

    def after_store(self):
        unpkd = unpack_instruction(self.instruction)
        if store_to_size(unpkd) is None:
            assert False, ("invalid call of after_load, !illegal transition!")

        offset = unpkd["offset"]
        if self.size is not None:
            assert self.size == int(store_to_size(unpkd) / 8)

        if self.direction == PENDING and self.store[L_L_B] is None and self.store[R_L_B] is None:  # first load-store pair
            self.store[L_L_B], self.store[L_U_B] = offset, offset + self.size
        elif self.direction == FORWARD:
            if offset == self.store[L_U_B]:
                self.store[L_U_B] += self.size
            elif offset == self.store[R_U_B]:
                self.store[R_U_B] += self.size
            elif offset == (self.store[R_U_B] - int(6 / self.size)):
                self.store[L_L_B], self.store[L_U_B] = offset, offset + self.size
            else:
                assert False, ("invalid call of after_store, !illegal transition!")
        elif self.direction == BACKWARD:
            if (offset + self.size) == self.store[L_L_B]:
                self.store[L_L_B] -= self.size
            elif (offset + self.size) == self.store[R_L_B]:
                self.store[R_L_B] -= self.size
            elif (offset + self.size) == (self.store[L_U_B] + (int(6 / self.size) - self.n) * self.size):
                self.store[R_L_B], self.store[R_U_B] = offset, offset + self.size
            else:
                assert False, ("invalid call of after_store, !illegal transition!")

        self.n += 1
        self.optimized_instructions[-1][self.instruction_id] = (self.instruction, "NOP")

    def finalize_optimized_intructions(self):
        instructions = sorted(self.optimized_instructions[-1].keys())

        load_inst = set_opcode(self.optimized_instructions[-1][instructions[0]][0], LOAD48)
        load_inst = modify_offset(load_inst, self.load[L_L_B])
        unpkd = unpack_instruction(load_inst)
        load_inst_str = "r"+str(get_output(unpkd))+" = *(uint48 *) (r"+str(get_inputs(unpkd)[0])+" + "+str(unpkd["offset"])+")"

        store_inst = set_opcode(self.optimized_instructions[-1][instructions[1]][0], STORE48)
        store_inst = modify_offset(store_inst, self.store[L_L_B])
        unpkd = unpack_instruction(store_inst)
        store_inst_str = "*(uint48 *) (r"+str(get_inputs(unpkd)[1])+" + "+str(unpkd["offset"])+") = r"+str(get_inputs(unpkd)[0])

        self.optimized_instructions[-1][instructions[0]] = (load_inst, load_inst_str)
        self.optimized_instructions[-1][instructions[1]] = (store_inst, store_inst_str)

        for key in instructions[2:]:
            self.optimized_instructions[-1][key] = (NOP, "NOP")

    def reset_state(self):
        self.load = {L_L_B: None, L_U_B: None, R_L_B: None, R_U_B: None}
        self.store = {L_L_B: None, L_U_B: None, R_L_B: None, R_U_B: None}
        self.direction = None
        self.n = 0
        self.size = None
