"""
Rate limiting configuration for Clarix API using SlowAPI.
"""

import os
from slowapi import Limiter
from slowapi.util import get_remote_address

redis_url = os.getenv("REDIS_URL")
if redis_url:
    limiter = Limiter(key_func=get_remote_address, storage_uri=redis_url)
else:
    # Default in-memory rate limiting
    limiter = Limiter(key_func=get_remote_address)
