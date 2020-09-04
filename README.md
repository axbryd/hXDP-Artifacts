Artifacts for "hXDP: Efficient Software Packet Processing on FPGA NICs".

To clone this repo:
```(bash)
$ git clone https://github.com/axbryd/hXDP-Artifacts.git
```

# Overview
* Getting Started 
* XDP results validation
* Program the NetFPGA-SUME 
* hXDP Microbenchmark validation
* Examples optimization
* hXDP examples validation

# Getting Started
In this section, we will depict the hardware and software infrastructure needed to validate the results on the paper.

## Hardware Requirements
We provide full-acces to our testbed with a NetFPGA-SUME and a machine used for traffic generation. SSH Public and Private Keys are provided in the HotCRP submission form.

To access:
```(bash)
$ ssh osdi20-aec@capoccino.netgroup.uniroma2.it
```
To add the new keys to your agent, follow [this](https://www.ssh.com/ssh/add) guide.

## Software Requirements
* Ubuntu 16.04 LTS (any newer LTS version of Ubuntu should do the job)

If you want to synthesize the bitstream for hXDP on your own, you can download the Vivado project [here](https://www.dropbox.com/s/kven1zrdnwi0n0a/OSDI20_hXDP.xpr.zip?dl=0).

You'll need to install also Xilinx Vivado Design Suite 2016.4 and obtain licenses, as explained [here](https://github.com/NetFPGA/NetFPGA-SUME-public/wiki/Getting-Started-Guide).
Synthesis can take up to 3 hours!

If you want the fast path, we provide the bitstream inside our testbed already.


# XDP Results Validation
In this section we will describe how to replicate the XDP Linux baseline tests. 
Most of the XDP programs used in the experiments are included in the Linux kernel tree (linux/samples/bpf), 
additional programs are provided in this repository (./xdp_progs). 

The experimental methodology and configuration follows what proposed in the XDP paper (https://dl.acm.org/doi/10.1145/3281411.3281443), 
our baseline results are combarable to what presented in the paper and in the paper repo (https://github.com/tohojo/xdp-paper/tree/master/benchmarks)

Results provided in the paper have been obtained using the following hardware/software configuration:

* DUT (Device Under Test): Intel Xeon E5-1630 v3 @3.70GHz, an Intel XL710 40GbE NIC, and running Linux v.5.6.4 with the i40e Intel NIC drivers. 

## XDP baseline how-to

In the following how-to we will assume that the Linux kernel source code has been downloaded in <kernel_source> directory and this repo has been cloned into <hXDP_repo>. For each test program we also indicate the characteristic of the network traffic used during the experiments 

## Kernel setup

download linux-5.6.4 source code from https://mirrors.edge.kernel.org/pub/linux/kernel/v5.x/linux-5.6.4.tar.gz
extract, compile and run the kernel (https://kernelnewbies.org/KernelBuild)

## Prepare and compile xdp programs

update the Linux XDP samples with the additional programs

```
cp <hXDP_repo>/xdp_progs/*  <kernel_source>/samples/bpf/
```

patch the Makefile for in tree compilation of the additional programs   

```
patch Makefile Makefile.patch
```

## Run the experiments

### xdp1

execute prog:
```
./xdp1 <eth_ifname>
```
traffic type: any

### xdp2 

execute prog:
```
./xdp1 <eth_ifname>
```
traffic type: UDP

### xdp_adjust_tail 

execute prog:
```
./xdp_adjust_tail -i <eth_ifname>
```
traffic type: ipv4, UDP

### xdp_router_ipv4

execute prog:
```
./xdp_router_ipv4 <eth_0_ifname> ... <eth_n_ifname>
```
traffic type: ipv4

### xdp_rxq_info 

execute prog:
```
./xdp_rxq_info -d <eth_ifname> --action XDP_DROP -s 3
```

### xdp_tx_iptunnel

execute prog:
```
./xdp_tx_iptunnel -i <eth_0_ifname> -a 192.168.0.2 -p 80 -s 10.0.0.1 -d 10.0.0.2 -m 0c:fd:fe:bb:3d:b0
```
### xdp_redirect_map
execute prog:
```
./xdp_redirect_map <eth_in_ifname> <eth_out_ifname> 
```
traffic type: any

### simple firewall

config:
* define internal (A_PORT) and external (B_PORT) interface index in xdp_fw_common.h 
* compile again the prog with ```make```

execute prog:
```
./xdp_fw
```
traffic type: ipv4, UDP

# hXDP Results validation

Our testbed is composed by two machines: *nino* and *ercole*. The first one is the one you access trough *ssh*, while the latter is attached to pane #3 of the *tmux* session created below.

To replicate the results, access our machine at *capoccino.netgroup.uniroma2.it*:
```(bash)
$ ssh osdi20-aec@capoccino.netgroup.uniroma2.it
```
Once you're in, create the the *tmux* session we've prepared for the AEC:
```(bash)
osdi20-aec@nino:~$ ./launch_tmux.sh
```
Here, you're presented with **4** panes. If you're unsure on how to use tmux, [here](https://tmuxcheatsheet.com/) is a quick reference.
 ## Program the NetFPGA-SUME
 In pane #0, execute ```./program_fpga.sh top_25_05_2020.bit```:
 
 ```(bash)
 osdi20-aec@nino:~/0_program_FPGA$ ./program_fpga.sh top_25_05_2020.bit 

****** Xilinx Microprocessor Debugger (XMD) Engine
****** XMD v2016.4 (64-bit)
  **** SW Build 1756540 on Mon Jan 23 19:11:19 MST 2017
    ** Copyright 1986-2016 Xilinx, Inc. All Rights Reserved.

WARNING: XMD has been deprecated and will be removed in future.
         XSDB replaces XMD and provides additional functionality.
         We recommend you switch to XSDB for commandline debugging.
         Please refer to SDK help for more details.

XMD% 
XMD% Configuring Device 1 (xc7vx690t) with Bitstream -- top_25_05_2020.bit
................10...............20...............30................40...............50...............60...............70................80...............90...............Successfully downloaded bit file.

JTAG chain configuration
--------------------------------------------------
Device   ID Code        IR Length    Part Name
 1       33691093           6        xc7vx690t
 2       16d7e093           8        xc2c512

0
XMD% 
Completed rescan PCIe information !

 ```
 ## Start the hXDP monitor program
 In pane #1, launch:
 ```(bash)
 osdi20-aec@nino:~/1_datapath_monitor$ ./hXDP_monitor.py 
 ```
 
 ## Prepare the traffic generation machine
 Navigate to pane #3 and launch ```./0_DPDK_bind_ifaces.sh```. The output should be:
 ```
 Network devices using DPDK-compatible driver
============================================
0000:03:00.0 'Ethernet 10G 2P X520 Adapter 154d' drv=igb_uio unused=ixgbe
0000:03:00.1 'Ethernet 10G 2P X520 Adapter 154d' drv=igb_uio unused=ixgbe
0000:81:00.0 'Ethernet 10G 2P X520 Adapter 154d' drv=igb_uio unused=ixgbe
0000:81:00.1 'Ethernet 10G 2P X520 Adapter 154d' drv=igb_uio unused=ixgbe

Network devices using kernel driver
===================================
0000:01:00.0 'I350 Gigabit Network Connection 1521' if=eno1 drv=igb unused=igb_uio *Active*
0000:01:00.1 'I350 Gigabit Network Connection 1521' if=eno2 drv=igb unused=igb_uio
0000:01:00.2 'I350 Gigabit Network Connection 1521' if=eno3 drv=igb unused=igb_uio
0000:01:00.3 'I350 Gigabit Network Connection 1521' if=eno4 drv=igb unused=igb_uio

No 'Crypto' devices detected
============================

No 'Eventdev' devices detected
==============================

No 'Mempool' devices detected
=============================

No 'Compress' devices detected
==============================
 ```
 # Run Microbenchmarks
 In this section, we describe how to recreate the microbenchmarks results depicted in the paper.
 ## XDP Drop
 In pane #2, let's program Sephirot's memory with the relevant ROM file, containing the XDP Drop program:
 ```
 osdi20-aec@nino:~/2_datapath_programming$ ./inject_sephirot_imem.py SPH_roms/XDP_DROP.bin
 ```
 You can double-check the proper injection by dumping the content of Sephirot's instruction memory:
 ```
osdi20-aec@nino:~/2_datapath_programming$ ./dump_sephirot_imem.py 10
NetFPGA-SUME Detected
Reaing from 0 Sephirot Core
0x0 :    0000000000000000 | 0000000000000000 | 00000001000000b7 | 0000000000000095 |
0x1 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
0x2 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
0x3 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
0x4 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
0x5 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
0x6 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
0x7 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
0x8 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
0x9 :    0000000000000000 | 0000000000000000 | 0000000000000000 | 0000000000000000 |
 ```
Where *10* is the number of Very-Long Instruction Words to be fetched form the memory.

We can now move to pane #3 to generate traffic ```osdi20-aec@ercole:~/3_traffic_generation$ ./1_throughput_test_64.sh```.

Moving on pane #1, we should see the datapath responding:
```
RECEIVED PACKETS: 446495634 pkts
XDP_DROP OCCURENCIES: 180722170 pkts
ARRIVAL RATE: 56.584462 Mpps
DROP RATE: 22.41349 Mpps
TX RATE: 0.0 Mpps
```
For the next benchmarks, since the steps are the same except for the ROM to be loaded and the test type, we just point out this details for the sake of brevity.

## XDP Drop w/ early exit
* ROM: ```XDP_DROP_early_exit.bin```
* Test: ```1_throughput_test_64.sh```

## XDP TX w/ early exit
* ROM: ```XDP_TX_early_exit.bin```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

# Run XDP examples on hXDP
Here we describe how to run the same examples depicted in the software section on hXDP. Before doing this, we describe how to *optimize* the original eBPF bytecode to run on Sephirot. Tests are runned as reported in the XDP Drop microbenchmark.

## Optimization
This is an optional step since all the ROMs are loaded inside the testbed.

## xdp1
* ROM: ```xdp1.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```


## xdp2
* ROM: ```xdp1.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

## xdp_adjust_tail


## xdp_router_ipv4
* ROM: ```xdp_router_ipv4.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

## xdp_rxq_info
* ROM: ```xdp_rxq_info.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

## xdp_tx_iptunnel

## xdp_redirect_map
* ROM: ```xdp_redirect_map_kern.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

## simple_firewall
* ROM: ```nec_udp_firewall.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```
