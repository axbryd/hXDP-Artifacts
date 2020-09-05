from file_reader import read_file
from file_writer import write_program_to_file
from optimizer_core import Optimizer
from os import listdir
from os.path import isfile, join
from ebpf_parser import *


def compute_parallelization_score(program, parallel_program):
    return {"original_rows": len(program),
            "parallelized_rows": len(parallel_program),}
    n_lanes = [0 for i in range(4)]

    for i in range(len(parallel_program)):
        used = 0
        for j in range(len(parallel_program[0])):
            if parallel_program[i][j] is not None:
                used += 1
        n_lanes[used] += 1

    return {"original_rows": len(program),
            "parallelized_rows": len(parallel_program),}
            #"speedup": float(len(program)) / float(len(parallel_program)),
            #"0_lane_time": 100 * float(n_lanes[0]) / float(len(parallel_program)),
            #"1_lane_time": 100 * float(n_lanes[1]) / float(len(parallel_program)),
            #"2_lanes_time": 100 * float(n_lanes[2]) / float(len(parallel_program)),
            #"3_lanes_time": 100 * float(n_lanes[3]) / float(len(parallel_program)),
            #}


def print_parallelization_score(parallelization_score):
    print()
    print("~ Original program #rows: " + str(parallelization_score["original_rows"]))
    print("~ Parallelized program #rows: " + str(parallelization_score["parallelized_rows"]))
    return
    print("~ Speedup: " + str("{0:.3f}".format(parallelization_score["speedup"])) + " x")
    print("~ 0_lane_time: " + str("{0:.3f}".format(parallelization_score["0_lane_time"])) + " %")
    print("~ 1_lane_time: " + str("{0:.3f}".format(parallelization_score["1_lane_time"])) + " %")
    print("~ 2_lanes_time: " + str("{0:.3f}".format(parallelization_score["2_lanes_time"])) + " %")
    print("~ 3_lanes_time: " + str("{0:.3f}".format(parallelization_score["3_lanes_time"])) + " %")
    print()


files = [f for f in listdir("xdp_prog_dump/") if isfile(join("xdp_prog_dump/", f)) and f == "xdp_adjust_tail"]

mean_speedup = 0
mean_unused_lanes = 0


def print_program(program):
    print()
    print("Program:")
    for inst in range(len(program)):
        print_unpkd(unpack_instruction(program[inst]), inst)
    print()

for file in files:
    print("====================================================")
    program_bin, program_str = read_file("xdp_prog_dump/" + file)

    print("File: " + file)
    print(" ~ with constraints")

    parallelizer = Optimizer(program_bin, program_str, filename=file, branch_all_lanes=True,
                             lane_forward_constraint=True, debug_print_blocks_pre_sched=True,
                             debug_print_blocks_pre_opt=False, debug_draw_cfg=True)

    parallelizer.optimize()

    #write_program_to_file(filename=file + ".out", parallel_program=parallelizer.resource_table)

    parallelization_score = compute_parallelization_score(program_bin, parallelizer.resource_table)
    print_parallelization_score(parallelization_score)

    #mean_speedup += parallelization_score["speedup"]


#print("====================================================")
#print("~ Mean speedup: " + str(mean_speedup / float(len(files))))