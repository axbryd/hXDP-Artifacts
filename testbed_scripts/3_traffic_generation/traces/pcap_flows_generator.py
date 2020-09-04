from scapy.all import *
from scapy.layers.inet import IP, UDP
from scapy.layers.l2 import Ether

try:
    from secrets import token_hex
except ImportError:
    from os import urandom

    def token_hex(nbytes=None):
        return urandom(nbytes).hex()

payloads = {}


def paylaod_generator(size, string='sal'):
    if size in payloads:
        return payloads[size]
    payload = ''
    for i in range(int(size/len(string))):
        payload += string
    for i in range(size%len(string)):
        payload += '.'
    payloads[size] = payload
    return payload


def rand_port():
    return random.randint(2000, 49151)


def rand_mac():
    mac = ""
    for i in range(6):
        mac += token_hex(1)
        if i != 5:
            mac += ":"
    return mac


def rand_ip():
    ip = ''
    for i in range(4):
        ip += str(random.randint(1, 255))
        if i != 3:
            ip += '.'
    return ip


def generate_flows(n_flows, pkt_size, string, filename):
    pkts = [None for i in range(n_flows)]
    for i in range(n_flows):
        pkts[i] = Ether(src=rand_mac(), dst=rand_mac())/IP(src=rand_ip(), dst=rand_ip())/\
              UDP(sport=rand_port(), dport=rand_port())/\
              Raw(load=paylaod_generator(pkt_size - 42, string))
    wrpcap(filename, pkts, append=False if i == 0 else True)

def main():
    sizes = [1500]
    flows = [100]
    strings = ['sal', 'penny', 'tonzula']
    threads = [None for i in range(len(sizes)*len(flows))]

    i = 0
    for size in sizes:
        for flow in flows:
            print("Generating "+str(size)+" Bytes, "+str(flow)+" flows")
            threads[i] = Thread(target=generate_flows, args=(flow, size, strings[i%3], str(flow)+"_flows_"+str(size)+'_bytes.pcap'))
            threads[i].start()
            i += 1

    for i in range(len(threads)):
        threads[i].join()
        print("Thread "+str(i)+" finished")

main()
