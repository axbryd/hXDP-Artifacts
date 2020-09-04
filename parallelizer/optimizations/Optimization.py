from transitions import Machine

DEFAULT_TRIGGER = "default_trigger"

SOURCE = "source"
DESTINATION = "dest"
CONDITIONS = "conditions"
UNLESS = "unless"
AFTER = "after"
TRIGGER = "trigger"


class Optimization(object):

    def __init__(self):
        self.optimized_instructions = [dict()]
        self.instruction = None
        self.instruction_id = None

    def get_optimized_instructions(self):
        return self.optimized_instructions

    def delete_last_optimized(self):
        self.optimized_instructions = self.optimized_instructions[:-1]

    def new_optimized_empty_list(self):
        self.optimized_instructions.append(dict())

    def parse_instruction(self, instruction, instruction_id):
        #print(instruction_id)
        self.instruction, self.instruction_id = instruction, instruction_id
        self.default_trigger()