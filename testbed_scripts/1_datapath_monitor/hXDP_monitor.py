#!/usr/bin/python3

import os
import sys
import subprocess
import time

FNULL = open(os.devnull, "w")

# Test presence of NetFPGA
retcode = subprocess.call(["./rwaxi"], stdout=FNULL, stderr=subprocess.STDOUT)

def cls():
    os.system('cls' if os.name=='nt' else 'clear')

if retcode == 1:
    print ("ERROR: NetFPGA-SUME not available on this system")
    exit(-1)

else:
    print("NetFPGA-SUME Detected")

############ READ FROM AXI ADDRESS FUNCTION ###############
def read_axi_addr(addr):
	result = subprocess.Popen(["./rwaxi", "-a", addr], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	readed_value = result.communicate()
	#print (readed_value[0].decode('utf-8').rstrip())
	return readed_value[0][2:].decode('utf-8').rstrip()
###########################################################

dropped_packtes_before = 0

while True:
    dropped_packets_before = int(read_axi_addr("0x80020004"),16)
    transmitted_packets_before = int(read_axi_addr("0x80020003"),16)
    received_packets_before = int(read_axi_addr("0x80020002"),16)

    time.sleep(1)

    dropped_packets_now = int(read_axi_addr("0x80020004"),16)
    transmitted_packets_now = int(read_axi_addr("0x80020003"),16)
    received_packets_now = int(read_axi_addr("0x80020002"),16)
    cls()
    
    print("RECEIVED PACKETS:", int(read_axi_addr("0x80020002"),16) , "pkts")
    print("XDP_DROP OCCURENCIES:", dropped_packets_now , "pkts")
    print("ARRIVAL RATE:",(received_packets_now - received_packets_before)/1000000, "Mpps")
    print("DROP RATE:",(dropped_packets_now - dropped_packets_before)/1000000, "Mpps")
    print("TX RATE:",(transmitted_packets_now - transmitted_packets_before)/1000000, "Mpps")


