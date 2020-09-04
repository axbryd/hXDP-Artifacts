--- Replay a pcap file.

local mg      = require "moongen"
local device  = require "device"
local memory  = require "memory"
local stats   = require "stats"
local log     = require "log"
local pcap    = require "pcap"
local limiter = require "software-ratecontrol"

function configure(parser)
	parser:argument("dev", "Device to use."):args(1):convert(tonumber)
	parser:argument("file1", "File 1 to replay."):args(1)
	parser:option("-r --rate-multiplier", "Speed up or slow down replay, 1 = use intervals from file, default = replay as fast as possible"):default(0):convert(tonumber):target("rateMultiplier")
	parser:flag("-l --loop", "Repeat pcap file.")
	local args = parser:parse()
	return args
end

function master(args)
	local dev = device.config{port = 0}
    local dev1 = device.config{port = 1}
    local dev2 = device.config{port = 2}
    local dev3 = device.config{port = 3}
	
    local rateLimiter
	device.waitForLinks()
	if args.rateMultiplier > 0 then
		rateLimiter = limiter:new(dev:getTxQueue(0), "custom")
	end
	mg.startTask("replay", dev:getTxQueue(0), args.file1, args.loop, rateLimiter, args.rateMultiplier)
	mg.startTask("replay", dev1:getTxQueue(0), args.file1, args.loop, rateLimiter, args.rateMultiplier)
    mg.startTask("replay", dev2:getTxQueue(0), args.file1, args.loop, rateLimiter, args.rateMultiplier)
    mg.startTask("replay", dev3:getTxQueue(0), args.file1, args.loop, rateLimiter, args.rateMultiplier)

    stats.startStatsTask{txDevices = {dev}}
    stats.startStatsTask{txDevices= {dev1}}
    stats.startStatsTask{txDevices = {dev2}}
    stats.startStatsTask{txDevices = {dev3}}
	mg.waitForTasks()
end

function replay(queue, file, loop, rateLimiter, multiplier)
	local mempool = memory:createMemPool(4096)
	local bufs = mempool:bufArray()
	local pcapFile = pcap:newReader(file)
	local prev = 0
	local linkSpeed = queue.dev:getLinkStatus().speed
	while mg.running() do
		local n = pcapFile:read(bufs)
		if n > 0 then
			if rateLimiter ~= nil then
				if prev == 0 then
					prev = bufs.array[0].udata64
				end
				for i, buf in ipairs(bufs) do
					-- ts is in microseconds
					local ts = buf.udata64
					if prev > ts then
						ts = prev
					end
					local delay = ts - prev
					delay = tonumber(delay * 10^3) / multiplier -- nanoseconds
					delay = delay / (8000 / linkSpeed) -- delay in bytes
					buf:setDelay(delay)
					prev = ts
				end
			end
		else
			if loop then
				pcapFile:reset()
			else
				break
			end
		end
		if rateLimiter then
			rateLimiter:sendN(bufs, n)
		else
			queue:sendN(bufs, n)
		end
	end
end

