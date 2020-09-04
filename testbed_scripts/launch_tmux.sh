#!/bin/sh
session="AEC"
tmux kill-session -t $session
tmux new-session -d -s $session -c './0_program_FPGA' -n 'program_FPGA'
tmux new-window -c './1_datapath_monitor' -n 'datapath_monitor'
tmux new-window -c './2_datapath_programming' -n 'datapath_programming'
tmux new-window -a -d -t $session -n traffic_generation
tmux send-keys -t $session:traffic_generation "ssh ercole" C-m
tmux send-keys -t $session:traffic_generation "cd 3_traffic_generation" C-m C-l
tmux attach-session -t $session

