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
 # Run tests
