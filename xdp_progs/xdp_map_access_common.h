#ifndef XDP_MAP_ACC
#define XDP_MAP_ACC

#define SIZE 1

struct dummy_key {
	__u8 key;
	// uncomment to change the key size
	// __u16 key;
	// __u32 key;
	// __u64 key;
	// __u8 extra[SIZE];
	// __u16 extra[SIZE];
	// __u32 extra[SIZE];
	// __u64 extra[SIZE];
};
#endif /* XDP_MAP_ACC */
