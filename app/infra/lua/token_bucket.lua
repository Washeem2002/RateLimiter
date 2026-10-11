-- Atomic token bucket rate limiter.
-- KEYS[1] = bucket key
-- ARGV[1] = capacity (max tokens)
-- ARGV[2] = refill rate (tokens per second)
-- ARGV[3] = now (unix seconds, float)
-- ARGV[4] = tokens requested
-- Returns: {allowed (1 or 0), remaining, retry_after_seconds}

local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call("HMGET", key, "tokens", "ts")
local tokens = tonumber(bucket[1])
local ts = tonumber(bucket[2])

if tokens == nil then
  tokens = capacity
  ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

local allowed = 0
local retry_after = 0

if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
else
  local deficit = requested - tokens
  retry_after = math.ceil(deficit / refill_rate)
end

redis.call("HMSET", key, "tokens", tokens, "ts", now)
local ttl = math.ceil(capacity / refill_rate) + 1
redis.call("EXPIRE", key, ttl)

return {allowed, tokens, retry_after}
