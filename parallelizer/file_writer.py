from ebpf_parser import little_to_big
from optimizer_core import INSTR_B

STR_FORMAT_32 = "{:016x}"
NUM_ROWS = 256


def write_program_to_file(filename, parallel_program):
    with open(filename, 'w') as file:
        for row in range(len(parallel_program)):
            for column in range(len(parallel_program[row]) -1, -1, -1):
                file.write(STR_FORMAT_32.format(little_to_big(parallel_program[row][column][INSTR_B] if parallel_program[row][column] is not None else 0)))
            if row < len(parallel_program) - 1:
                file.write("\n")

        if NUM_ROWS - len(parallel_program) < 0:
            print("Error the parallelized program is longer than the available memory")
            exit(-1)
        elif NUM_ROWS - len(parallel_program) > 0:
            file.write("\n")
            for row in range(NUM_ROWS - len(parallel_program)):
                for column in range(len(parallel_program[0]) - 1, -1, -1):
                    file.write(STR_FORMAT_32.format(0))
                if row < NUM_ROWS - len(parallel_program) - 1:
                    file.write("\n")





