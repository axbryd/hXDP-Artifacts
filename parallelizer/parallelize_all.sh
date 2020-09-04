#!/bin/bash

for file in ./xdp_prog_dump/*
do
      python3 parallelizer.py -i "$file" &> /dev/null
done
rmdir out
mkdir out
mv ./xdp_prog_dump/*.out ./out
