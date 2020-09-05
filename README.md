# hXDP repo

This repository contains the artifact for the paper "hXDP: Efficient Software Packet Processing on FPGA NICs":

* **hXDP datapath** implementation on NetFPGA
* **optimizing-compiler** used to translate eBPF bytecode to the hXDP extended eBPF Instruction-set 

We provide the necessary documentation and tools to replicate the paper results. 
In addition we provide access to a machine equipped with a NetFPGA and configured to execute the experiments. 

To replicate the results presented in the paper is it possible to follow two different paths:
* [access our pre-configured testbed and use our environment](#Experiments-replication) 
* [follow the README and configure hXDP from scratch](#Requisites)

# Repo organization 

* [hXDP datapath](https://zenodo.org/record/4015082#.X1I-FGczadY): link to Zenodo repo where it is possible to download the code necessary  to synthesize the hXDP bitstream. The size of the project is relatively big so the source code is not included in this repo.
* **parallelizer**: this directory contains the hXPD compiler and the [XDP bytecode](parallelizer/xdp_prog_dump/) used as input for the compiler .
* **testbed_scripts**: this directory contains scripts that can be used to replicate the paper experiments on our testbed, the compiled [XDP roms](testbed_scripts/2_datapath_programming/SPH_roms) to be executed on the hXDP datapath and the [hXDP bitcode](testbed_scripts/0_program_FPGA/top_25_05_2020.bit).
* **xdp_progs**: this directory contains the source code of the XDP programs used in the evaluation that are not included in the Linux kernel source tree.

# Requisites

To facilitate the testing of the artifacts we provide full-acces to our testbed with a NetFPGA-SUME and a machine used for traffic generation. The machine also includes the the synthetized hXDP bitstream. 

SSH Public and Private Keys are provided in the HotCRP submission form.

To access:
```(bash)
$ ssh osdi20-aec@capoccino.netgroup.uniroma2.it
```
To add the new keys to your agent, follow [this](https://www.ssh.com/ssh/add) guide.

Requisites for testing hXDP on your own are provided below.

## Hardware

A NetFPGA-SUME board is required to evaluate the artifact. 


## Software

* Ubuntu 16.04 LTS (any newer LTS version of Ubuntu should do the job)
* ```python 3```
    * Packages: ```networkx```, ```transitions```
* ```llvm``` (ver >= 6)

If you want to synthesize the bitstream for hXDP on your own, you can download the Vivado project [here](https://zenodo.org/record/4015082#.X1I-FGczadY).

You'll need to install also Xilinx Vivado Design Suite 2016.4 and obtain licenses, as explained [here](https://github.com/NetFPGA/NetFPGA-SUME-public/wiki/Getting-Started-Guide).
Synthesis can take up to 3 hours!



# Install

``` 
git clone https://github.com/axbryd/hXDP-Artifacts.git
```

# How to 

We will now describe how to compile and load an XDP program into the hXDP datapath. We assume that the environment to compile XDP programs is available and configured.

### Dump eBPF bytecode 

In order to compile the hXDP roms the hXDP compiler needs as input the xdp program bytecode.
```
llvm-objdump -S <xdp_prog>.o > <xdp_prog>.bytecode
```
If you want to skip this step, the Bytecodes of xdp programs used in the paper evaluation are already provided [here](parallelizer/xdp_prog_dump/) 

### Generate XDP programs ROM 

```
python3 ./parallelizer/parallelizer.py -i <xdp_prog>.o
```

If you want to skip this step, ROMs used in the paper evaluation are already provided [here](testbed_scripts/2_datapath_programming/SPH_roms)

### Load hXDP datapath bitstream on the NetFPGA
```
./testbed_scripts/0_program_FPGA/program_fpga.sh ./testbed_scripts/0_program_FPGA/top_25_05_2020.bit
```
### Load ROM
```
./testbed_scripts/2_datapath_programming/inject_sephirot_imem.py ./testbed_scripts/2_datapath_programming/SPH_roms/XDP_DROP.bin
```
### Read/Write maps
Access to maps from userspace is provided through a simple script (reads) and "manually" (writes). The integration of hXDP with standard Linux tools, such as [bpftools](https://www.mankier.com/8/bpftool), for map access is an ongoing work and will be included in the next release.

#### read

```
./testbed_scripts/2_datapath_programming/dump_maps.py <n>
```

Where \<n> is the number of desired output lines

#### write
Write 32 bit of content (-w \<content>) ant the specified address (-a \<address>) 
```
./testbed_scripts/2_datapath_programming/rwaxi -a 0x80010000 -w 0x2
```
Write the commit bit to finalize the write
```
./testbed_scripts/2_datapath_programming/rwaxi -a 0x800100ff -w 0x1
```
Check the result
```
./testbed_scripts/2_datapath_programming/dump_maps.py 1
```

# Experiments replication

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
 ## Run Microbenchmarks
 In this section, we describe how to recreate the microbenchmarks results depicted in the paper.
 ### XDP Drop
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
For the next benchmarks, since the steps are the same except for the ROM to be loaded and the test type, we just point out these details for the sake of brevity.

### XDP Drop w/ early exit
* ROM: ```XDP_DROP_early_exit.bin```
* Test: ```1_throughput_test_64.sh```

### XDP TX w/ early exit
* ROM: ```XDP_TX_early_exit.bin```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

## Run XDP examples on hXDP
Here we describe how to run the same examples depicted in the software section on hXDP. Before doing this, we describe how to *compile* and *optimize* the original eBPF bytecode to run on Sephirot. Tests are run as reported in the XDP Drop microbenchmark.

### Compilation - Optimization (optional)
This is an optional step since all the ROMs are provided in the repo and inside the testbed.

You can find the parallelizer inside the relevant folder in this repo. To compile and optimize all the examples we've seen in the previous section, run ```./parallelize_all.sh```. You find the generated output products inside the ```out``` sub-folder.

### xdp1
* ROM: ```xdp1.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```


### xdp2
* ROM: ```xdp1.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

### xdp_adjust_tail


### xdp_router_ipv4
* ROM: ```xdp_router_ipv4.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

### xdp_rxq_info
* ROM: ```xdp_rxq_info.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

### xdp_tx_iptunnel

### xdp_redirect_map
* ROM: ```xdp_redirect_map_kern.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```

### simple_firewall
* ROM: ```nec_udp_firewall.bin.out```
* Test: ```1_throughput_test_64.sh, 2_latency_minimum_size.sh, 3_latency_maximum_size.sh```


## Linux Baseline 

In this section we will describe how to replicate the XDP Linux baseline tests. 
Most of the XDP programs used in the experiments are included in the Linux kernel tree (linux/samples/bpf), additional programs are provided in this repository. 

The experimental methodology and configuration follows what proposed in the XDP paper (["The eXpress data path: fast programmable packet processing in the operating system kernel"](https://dl.acm.org/doi/10.1145/3281411.3281443), 
our baseline results are combarable to what presented in the paper and in the paper [repo](https://github.com/tohojo/xdp-paper/tree/master/benchmarks)

Results provided in the paper have been obtained using the following hardware/software configuration:

* DUT (Device Under Test): Intel Xeon E5-1630 v3 @3.70GHz, an Intel XL710 40GbE NIC, and running Linux v.5.6.4 with the i40e Intel NIC drivers. 

Unfortunately we cannot provide remote access to such machine. 

In the following paragraph we will assume that the Linux kernel source code has been downloaded in <kernel_source> directory and this repo has been cloned into <hXDP_repo>. For each test program we also indicate the characteristic of the network traffic used during the experiments 

### Kernel setup

Download linux-5.6.4 source code from [here](https://mirrors.edge.kernel.org/pub/linux/kernel/v5.x/linux-5.6.4.tar.gz) extract, compile and run the kernel. If you are not familiar with kernel compilation follow the instructions provided [here](https://kernelnewbies.org/KernelBuild)

### Prepare and compile xdp programs

Update the Linux XDP samples with the additional programs
```
cp <hXDP_repo>/xdp_progs/*  <kernel_source>/samples/bpf/
```
Patch the Makefile for in tree compilation of the additional programs   
```
patch Makefile Makefile.patch
```

### Run the experiments
#### xdp1
execute prog:
```
./xdp1 <eth_ifname>
```
traffic type: any
#### xdp2 
execute prog:
```
./xdp1 <eth_ifname>
```
traffic type: UDP
#### xdp_adjust_tail 
execute prog:
```
./xdp_adjust_tail -i <eth_ifname>
```
traffic type: ipv4, UDP
#### xdp_router_ipv4
execute prog:
```
./xdp_router_ipv4 <eth_0_ifname> ... <eth_n_ifname>
```
traffic type: ipv4
#### xdp_rxq_info 
execute prog:
```
./xdp_rxq_info -d <eth_ifname> --action XDP_DROP -s 3
```
#### xdp_tx_iptunnel
execute prog:
```
./xdp_tx_iptunnel -i <eth_0_ifname> -a 192.168.0.2 -p 80 -s 10.0.0.1 -d 10.0.0.2 -m 0c:fd:fe:bb:3d:b0
```
#### xdp_redirect_map
execute prog:
```
./xdp_redirect_map <eth_in_ifname> <eth_out_ifname> 
```
traffic type: any
#### simple firewall
config:
* define internal (A_PORT) and external (B_PORT) interface index in xdp_fw_common.h 
* compile again the prog with ```make```
execute prog:
```
./xdp_fw
```
traffic type: ipv4, UDP
