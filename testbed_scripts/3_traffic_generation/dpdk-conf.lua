-- Configuration for all DPDK command line parameters.
-- See DPDK documentation at http://dpdk.org/doc/guides/testpmd_app_ug/run_app.html for details.
-- libmoon tries to choose reasonable defaults, so this config file can almost always be empty.
-- Be careful when running libmoon in a VM that also uses another virtio NIC, e.g., for internet access.
-- In this case it may be necessary to use the blacklist or whitelist features in some configurations.
DPDKConfig {
	-- configure the CPU cores to use, default: all cores
	--cores = {2,4,6,8,10,12},
	cores = {3,5,2,4,8,10,12},
	
	-- max number of shared tasks running on core 0
	--sharedCores = 8,

	-- black or whitelist devices to limit which PCI devs are used by DPDK
	-- only one of the following examples can be used
	--pciWhitelist = {"0000:03:00.1"},
	pciWhitelist = {"0000:81:00.1", "0000:03:00.1","0000:81:00.0", "0000:03:00.0"},
	--pciWhitelist = {"0000:81:00.0", "0000:81:00.1"},
	
	-- arbitrary DPDK command line options
	-- the following configuration allows multiple DPDK instances (use together with pciWhitelist)
	-- cf. http://dpdk.org/doc/guides/prog_guide/multi_proc_support.html#running-multiple-independent-dpdk-applications
	cli = {
		"-m", "512",
        --"--huge-dir", "/mnt/huge1G",
	}

}
