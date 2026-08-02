import time
import threading


class TokenBucket:
    """
    Token bucket rate limiter.

    - The bucket holds up to `capacity` tokens.
    - Each request consumes 1 token.
    - Tokens refill at `refill_rate` per second.
    - If the bucket is empty, the request is denied.

    This allows short bursts (up to capacity) while capping the
    long-run average rate.
    """

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity          # start full
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()    # safe under concurrent requests

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill

            # Add tokens for the time that has passed, up to capacity
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


class RateLimiterRegistry:
    """Keeps one TokenBucket per API key."""

    def __init__(self):
        self.buckets = {}
        self.lock = threading.Lock()

    def get_bucket(self, key_hash: str, rate_limit_per_min: int) -> TokenBucket:
        with self.lock:
            if key_hash not in self.buckets:
                # capacity = the per-minute limit (allows a full-minute burst)
                # refill_rate = limit / 60 tokens per second
                self.buckets[key_hash] = TokenBucket(
                    capacity=rate_limit_per_min,
                    refill_rate=rate_limit_per_min / 60.0,
                )
            return self.buckets[key_hash]


# One global registry for the whole app
registry = RateLimiterRegistry()