"""
Simple in-memory cache with TTL support
"""

import time
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """A single cache entry with expiration time"""
    value: Any
    expires_at: float


@dataclass
class SimpleCache:
    """
    Simple in-memory cache with TTL (Time To Live) support.
    
    Attributes:
        default_ttl: Default time-to-live in seconds (default: 300 = 5 minutes)
    """
    default_ttl: int = 300
    _cache: dict[str, CacheEntry] = field(default_factory=dict)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache if it exists and hasn't expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        entry = self._cache.get(key)
        if entry is None:
            return None
        
        if time.time() > entry.expires_at:
            # Entry has expired, remove it
            del self._cache[key]
            return None
        
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default_ttl if not specified)
        """
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if key didn't exist
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all entries from cache"""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry.expires_at
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


# Global cache instance
_global_cache = SimpleCache(default_ttl=300)


def get_cache() -> SimpleCache:
    """Get the global cache instance"""
    return _global_cache
