#!/bin/bash

if [ $# -ne 1 ]; 
    then echo "illegal number of parameters"
    exit
fi

#sudo echo "fpga -f $1" | /opt/Xilinx/SDK/2016.4/bin/xmd
sudo rmmod sume_riffa && echo "fpga -f $1 " | /opt/Xilinx/SDK/2016.4/bin/xmd && sleep 1 && sudo /home/sal/pci_rescan_run.sh && sudo insmod /lib/modules/4.11.2-041102-generic/extra/sume_riffa.ko # && ./monitor-FB.out 
