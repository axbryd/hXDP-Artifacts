#!/bin/bash
sudo dpdk-devbind -u 0000:03:00.0 &> /dev/null
sudo dpdk-devbind -u 0000:03:00.1 &> /dev/null
sudo dpdk-devbind -u 0000:81:00.0 &> /dev/null
sudo dpdk-devbind -u 0000:81:00.1 &> /dev/null
sudo dpdk-devbind -b igb_uio 0000:03:00.0 &> /dev/null
sudo dpdk-devbind -b igb_uio 0000:03:00.1 &> /dev/null
sudo dpdk-devbind -b igb_uio 0000:81:00.0 &> /dev/null
sudo dpdk-devbind -b igb_uio 0000:81:00.1 &> /dev/null
clear
sudo dpdk-devbind -s
