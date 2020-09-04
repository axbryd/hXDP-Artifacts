#!/usr/bin/python3

import os
import sys
import subprocess
import time

MAX_LINES = 256
FNULL = open(os.devnull, "w")

if len(sys.argv) < 2:
	print("ERROR: Need to specify .bin file")
	exit(-1)

# Test presence of NetFPGA
retcode = subprocess.call(["./rwaxi"], stdout=FNULL, stderr=subprocess.STDOUT)

if retcode == 1:
    print ("ERROR: NetFPGA-SUME not available on this system")
    exit(-1)

else:
    print("NetFPGA-SUME Detected")

def cls():
    os.system('cls' if os.name=='nt' else 'clear')

############ WRITE TO AXI ADDRESS FUNCTION ###############
def write_axi_addr(addr, val):
	result = subprocess.Popen(["./rwaxi", "-a", addr, "-w", "0x" + val], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	readed_value = result.communicate()
	result = subprocess.Popen(["./rwaxi", "-a", addr], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	readed_value = result.communicate()
	#print (readed_value[0].decode('utf-8').rstrip())
	return readed_value[0][2:].decode('utf-8').rstrip()
###########################################################

bin_file = open(sys.argv[1], 'r')
instructions = bin_file.readlines()

for i in range (0, MAX_LINES):
#	print(instructions[i][0:8] + instructions[i][8:16] +instructions[i][16:24] +instructions[i][24:32] + instructions[i][32:40] +instructions[i][40:48] +instructions[i][48:56] + instructions[i][56:].strip() )
		
	if (i < 16):
		write_axi_addr("0x80000"+str(hex(i)[2:])+"00",  instructions[i][56:].strip())
#		time.sleep(0.1)
		write_axi_addr("0x80000"+str(hex(i)[2:])+"04",  instructions[i][48:56])
#		time.sleep(0.1)
		write_axi_addr("0x80000"+str(hex(i)[2:])+"08",  instructions[i][40:48])
#		time.sleep(0.1)
		write_axi_addr("0x80000"+str(hex(i)[2:])+"0c",  instructions[i][32:40])
#		time.sleep(0.1)
		write_axi_addr("0x80000"+str(hex(i)[2:])+"10",  instructions[i][24:32])
#		time.sleep(0.1)
		write_axi_addr("0x80000"+str(hex(i)[2:])+"14",  instructions[i][16:24])
#		time.sleep(0.1)
		write_axi_addr("0x80000"+str(hex(i)[2:])+"18",  instructions[i][8:16])
#		time.sleep(0.1)
		write_axi_addr("0x80000"+str(hex(i)[2:])+"1c",  instructions[i][0:8])
#		time.sleep(0.1)
		write_axi_addr("0x80000"+str(hex(i)[2:])+"ff",  "1")
	else:
		write_axi_addr("0x8000"+str(hex(i)[2:])+"00", instructions[i][56:].strip())
#		time.sleep(0.1)
		write_axi_addr("0x8000"+str(hex(i)[2:])+"04", instructions[i][48:56])
#		time.sleep(0.1)
		write_axi_addr("0x8000"+str(hex(i)[2:])+"08", instructions[i][40:48])
#		time.sleep(0.1)
		write_axi_addr("0x8000"+str(hex(i)[2:])+"0c", instructions[i][32:40])
#		time.sleep(0.1)
		write_axi_addr("0x8000"+str(hex(i)[2:])+"10", instructions[i][24:32])
#		time.sleep(0.1)
		write_axi_addr("0x8000"+str(hex(i)[2:])+"14", instructions[i][16:24])
#		time.sleep(0.1)
		write_axi_addr("0x8000"+str(hex(i)[2:])+"18", instructions[i][8:16])
#		time.sleep(0.1)
		write_axi_addr("0x8000"+str(hex(i)[2:])+"1c", instructions[i][0:8])
#		time.sleep(0.1)
		write_axi_addr("0x8000"+str(hex(i)[2:])+"ff", "1")

	cls()
	print ("Injecting....Percentage Completed:", int(round(i/(MAX_LINES-1)*100,0)),"%")

print("Done", u'\u2713')
		    

