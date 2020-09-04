import argparse, os
from file_reader import read_file
from file_writer import write_program_to_file
from optimizer_core import Optimizer

parser = argparse.ArgumentParser(description='Parallelize eBPF program')
parser.add_argument('-i', '--input', type=str, required=True, help='eBPF dump input file name')
parser.add_argument('-o', '--output', type=str, help='parallelized bin file name')

args = parser.parse_args()
in_file = args.input

out_file = os.path.splitext(args.input)[0]+".bin" if args.output is None else args.output

program_bin, program_str = read_file(in_file)

parallelizer = Optimizer(program_bin, program_str, filename=os.path.splitext(args.input)[0], branch_all_lanes=False, lane_forward_constraint=True)

parallelizer.optimize()

write_program_to_file(filename=out_file + ".out", parallel_program=parallelizer.resource_table)