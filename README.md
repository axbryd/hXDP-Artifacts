Artifacts for "hXDP: Efficient Software Packet Processing on FPGA NICs".

To clone this repo:
```(bash)
$ git clone https://github.com/axbryd/hXDP-Artifacts.git
$ git checkout camera-ready
```

# Overview
* Getting Started (10 human-minutes + 5 compute-minutes)
* Program the NetFPGA-SUME (2 human-minutes + 1 compute-hour)
* Microbenchmark validation (5 human-minutes + 3 compute-hours) 
* Examples optimization (30 human-minutes + 5 compute-minutes)
* Examples validation (20 human-minutes)

# Getting Started (10 human-minutes + 5 compute-minutes)
In this section, we will depict the hardware and software infrastructure needed to validate the results on the paper.

## Hardware Requirements

* A [NetFPGA-SUME](https://github.com/NetFPGA/NetFPGA-SUME-public/wiki/Getting-Started-Guide) Board connected to the host system's PCI-e bus
* A 4x10Gbe NIC (in our tests, we've used a ...)

The two boards need to be conncted back-back-to-back

## Software Requirements
* Ubuntu 16.04 LTS (any newer LTS version of Ubuntu should do the job)
* The NetFPGA SUME development environment following the information available at https://github.com/NetFPGA/NetFPGA-SUME-public/wiki
* Xilinx Vivado Design Suite 2016.4 (for programming tools)
* Data Plane Development Kit, tutorial [here](https://doc.dpdk.org/guides/linux_gsg/intro.html)
* Moongen Packet Generator, tutorial [here](https://github.com/emmericp/MoonGen)

