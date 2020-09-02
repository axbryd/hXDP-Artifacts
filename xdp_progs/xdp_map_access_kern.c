/* Copyright (c) 2016 PLUMgrid
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of version 2 of the GNU General Public
 * License as published by the Free Software Foundation.
 */
#define KBUILD_MODNAME "foo"
#include <uapi/linux/bpf.h>
#include <linux/in.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <bpf/bpf_helpers.h>

#include "xdp_map_access_common.h"


struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_HASH);
	__type(key, struct dummy_key);
	__type(value, long);
	__uint(max_entries, 256);
} rxcnt SEC(".maps");

static void swap_src_dst_mac(void *data)
{
	unsigned short *p = data;
	unsigned short dst[3];

	dst[0] = p[0];
	dst[1] = p[1];
	dst[2] = p[2];
	p[0] = p[3];
	p[1] = p[4];
	p[2] = p[5];
	p[3] = dst[0];
	p[4] = dst[1];
	p[5] = dst[2];
}

SEC("xdp_map_acces")
int xdp_prog1(struct xdp_md *ctx)
{
	void *data_end = (void *)(long)ctx->data_end;
	void *data = (void *)(long)ctx->data;
	struct ethhdr *eth = data;
	struct dummy_key key = {0};
	int rc = XDP_DROP;
	long *value;
	u16 h_proto;
	u64 nh_off;
	long dummy_value = 1;

	nh_off = sizeof(*eth);
	if (data + nh_off > data_end)
		return rc;

//	swap_src_dst_mac(data);
//	rc = XDP_TX;

	h_proto = eth->h_proto;
	key.key = 23;
	
	value = bpf_map_lookup_elem(&rxcnt, &key);
	if (value){
		*value += 1;
	}else{
		bpf_map_update_elem(&rxcnt, &key, &dummy_value, BPF_ANY);
	}
	return rc;
}

char _license[] SEC("license") = "GPL";
