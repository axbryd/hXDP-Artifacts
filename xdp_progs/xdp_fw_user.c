#include <linux/bpf.h>
#include <linux/if_link.h>
#include <assert.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <libgen.h>
#include <sys/resource.h>
#include <arpa/inet.h>


#include "bpf_util.h"
#include <bpf/bpf.h>
#include <bpf/libbpf.h>

#include "xdp_fw_common.h"

static int ifindex_in = A_PORT;
static int ifindex_out = B_PORT;

static __u32 prog_id;
static __u32 xdp_flags = XDP_FLAGS_DRV_MODE;
static int flow_map_fd;

static void int_exit(int sig)
{
	bpf_set_link_xdp_fd(ifindex_out, -1, xdp_flags);
	bpf_set_link_xdp_fd(ifindex_in, -1, xdp_flags);
	exit(0);
}

static void poll_stats(int interval)
{
	while (1) {
		struct flow_ctx_table_key flow_key      = {0};
		struct flow_ctx_table_key next_flow_key = {0};
		struct flow_ctx_table_leaf flow_leaf    = {0};


		printf("\n");
		while (bpf_map_get_next_key(flow_map_fd, &flow_key, &next_flow_key) == 0) {
			bpf_map_lookup_elem(flow_map_fd, &next_flow_key, &flow_leaf);
			printf("Flow table: [ ip_proto %d | ip s %x  d %x | l4 s %x d %x | in %d out %d]\n" ,
			next_flow_key.ip_proto,next_flow_key.ip_src,next_flow_key.ip_dst,next_flow_key.l4_src,next_flow_key.l4_dst,flow_leaf.in_port,flow_leaf.out_port);
			flow_key = next_flow_key;
		}

		sleep(interval);
	}
}

int main(int argc, char **argv)
{
	struct rlimit r = {RLIM_INFINITY, RLIM_INFINITY};
	struct bpf_prog_load_attr prog_load_attr = {
		.prog_type	= BPF_PROG_TYPE_XDP,
	};
	struct bpf_prog_info info = {};
	__u32 info_len = sizeof(info);
	int prog_fd;
	struct bpf_object *obj;
	int ret,  key = 0;
	char filename[256];
	int tx_port_map_fd;

	if (setrlimit(RLIMIT_MEMLOCK, &r)) {
		perror("setrlimit(RLIMIT_MEMLOCK)");
		return 1;
	}

	snprintf(filename, sizeof(filename), "%s_kern.o", argv[0]);
	prog_load_attr.file = filename;

	if (bpf_prog_load_xattr(&prog_load_attr, &obj, &prog_fd))
		return 1;

	tx_port_map_fd = bpf_object__find_map_fd_by_name(obj, "tx_port");
	if (tx_port_map_fd < 0) {
		printf("bpf_object__find_map_fd_by_name failed\n");
		return 1;
	}

	flow_map_fd = bpf_object__find_map_fd_by_name(obj, "flow_ctx_table");
	if (flow_map_fd < 0) {
		printf("bpf_object__find_map_fd_by_name failed\n");
		return 1;
	}

	if (bpf_set_link_xdp_fd(ifindex_in, prog_fd, xdp_flags) < 0) {
		printf("ERROR: link set xdp fd failed on %d\n", ifindex_in);
		return 1;
	}

	if (bpf_set_link_xdp_fd(ifindex_out, prog_fd, xdp_flags) < 0) {
		printf("ERROR: link set xdp fd failed on %d\n", ifindex_in);
		return 1;
	}

	ret = bpf_obj_get_info_by_fd(prog_fd, &info, &info_len);
	if (ret) {
		printf("can't get prog info - %s\n", strerror(errno));
		return ret;
	}
	prog_id = info.id;

	signal(SIGINT, int_exit);
	signal(SIGTERM, int_exit);
	
	key = B_PORT;
	ifindex_out = B_PORT;
	
	ret = bpf_map_update_elem(tx_port_map_fd, &key, &ifindex_out, 0);
	if (ret) {
		perror("bpf_update_elem");
		goto out;
	}


	poll_stats(10);
	
out:
	return 0;


}
