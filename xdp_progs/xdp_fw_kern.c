#define KBUILD_MODNAME "foo"
#include <uapi/linux/bpf.h>
#include <linux/in.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <linux/if_vlan.h>
#include <linux/ip.h>
#include <linux/ipv6.h>
#include <bpf/bpf_helpers.h>

#include "xdp_fw_common.h"


//#define DEBUG 1
#ifdef  DEBUG

#define bpf_debug(fmt, ...)						\
			({							\
				char ____fmt[] = fmt;				\
				bpf_trace_printk(____fmt, sizeof(____fmt),	\
				##__VA_ARGS__);			\
			})
#else
#define bpf_debug(fmt, ...) { } while (0)
#endif

static inline void biflow(struct flow_ctx_table_key *flow_key){
	u32 swap;
	if (flow_key->ip_src > flow_key->ip_dst){
		swap = flow_key->ip_src;
		flow_key->ip_src = flow_key->ip_dst;
		flow_key->ip_dst = swap;
	}

	if (flow_key->l4_src  > flow_key->l4_dst){
		swap = flow_key->l4_src;
		flow_key->l4_src = flow_key->l4_dst;
		flow_key->l4_dst = swap;
	}

}

struct bpf_map_def SEC("maps") tx_port = {
	.type = BPF_MAP_TYPE_DEVMAP,
	.key_size = sizeof(int),
	.value_size = sizeof(int),
	.max_entries = 10,
};

struct bpf_map_def SEC("maps") flow_ctx_table = {
	.type = BPF_MAP_TYPE_HASH,
	.key_size = sizeof(struct flow_ctx_table_key),
	.value_size = sizeof(struct flow_ctx_table_leaf),
	.max_entries = 1024,
};


SEC("xdp_fw")
int xdp_fw_prog(struct xdp_md *ctx)
{
	
	void* data_end = (void*)(long)ctx->data_end;
	void* data         = (void*)(long)ctx->data;
	
	struct flow_ctx_table_leaf new_flow = {0};
	struct flow_ctx_table_key flow_key  = {0};
	struct flow_ctx_table_leaf *flow_leaf;

	struct ethhdr *ethernet;
	struct iphdr        *ip;
	struct udphdr      *l4;

	int ingress_ifindex;
	uint64_t nh_off = 0;
	u8 port_redirect = 0;
	int ret = XDP_PASS;
	u8 is_new_flow = 0;
	int vport = 0;
	/*  remember, to see printk 
	 * sudo cat /sys/kernel/debug/tracing/trace_pipe
	 */
	bpf_debug("I'm in the pipeline\n");

ethernet: {
	ethernet = data ;
	nh_off = sizeof(*ethernet);
	if (data  + nh_off  > data_end)
		goto EOP;
	
	
	ingress_ifindex = ctx->ingress_ifindex;
//	if (!ntohs(ethernet->h_proto))
//		goto EOP;
	
	bpf_debug("I'm eth\n");
	switch (ntohs(ethernet->h_proto)) {
		case ETH_P_IP:    goto ip;
		default:          goto EOP;
	}
}

ip: {
	bpf_debug("I'm ip\n");
	
	ip = data + nh_off;
	nh_off +=sizeof(*ip);
	if (data + nh_off  > data_end)
		goto EOP;

	switch (ip->protocol) {
		case IPPROTO_TCP: goto l4;
		case IPPROTO_UDP: goto l4;
		default:          goto EOP;
	}
}

l4: {
	bpf_debug("I'm l4\n");
	l4 = data + nh_off;
	nh_off +=sizeof(*l4);
	if (data + nh_off  > data_end)
		goto EOP;
}

	bpf_debug("extracting flow key ... \n");
	/* flow key */
	flow_key.ip_proto = ip->protocol;

	flow_key.ip_src = ip->saddr;
	flow_key.ip_dst = ip->daddr;
	flow_key.l4_src = l4->source;
	flow_key.l4_dst = l4->dest;

	biflow(&flow_key);
	



	if (ingress_ifindex == B_PORT){
		flow_leaf = bpf_map_lookup_elem(&flow_ctx_table, &flow_key);
			
		if (flow_leaf)
			return bpf_redirect_map(&tx_port,flow_leaf->out_port, 0);
		else 
			return XDP_DROP;
	} else {
		flow_leaf = bpf_map_lookup_elem(&flow_ctx_table, &flow_key);
			
		if (!flow_leaf){
			new_flow.in_port = B_PORT;
			new_flow.out_port = A_PORT; //ctx->ingress_ifindex ;
			bpf_map_update_elem(&flow_ctx_table, &flow_key, &new_flow, BPF_ANY);
		}
		
		return bpf_redirect_map(&tx_port, B_PORT, 0);
	}


EOP:
	return XDP_DROP;

}



char _license[] SEC("license") = "GPL";
