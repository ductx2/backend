"""
Groq API Key Rotator
Smart rotation system for multiple Groq API keys with failure tracking and recovery

Created: 2025-09-11
Purpose: Eliminate single point of failure with intelligent key rotation
Features: Round-robin selection, failure tracking, automatic recovery, health monitoring
"""

import logging
import time
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class APIKeyStatus:
    """Track individual API key status and metrics"""
    key: str
    is_active: bool = True
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0
    
    @property
    def is_healthy(self) -> bool:
        """Determine if key is considered healthy"""
        # Key is healthy if:
        # 1. It's marked as active
        # 2. Success rate is above 50% (for keys with >10 requests)
        # 3. No recent failures (last 15 minutes)
        if not self.is_active:
            return False
            
        if self.total_requests > 10 and self.success_rate < 50:
            return False
            
        if self.last_failure_time:
            time_since_failure = datetime.utcnow() - self.last_failure_time
            if time_since_failure < timedelta(minutes=15):
                return False
                
        return True
    
    def record_success(self):
        """Record a successful API call"""
        self.total_requests += 1
        self.successful_requests += 1
        self.last_success_time = datetime.utcnow()
        self.is_active = True  # Reactivate on success
        
    def record_failure(self, error_type: str = "unknown"):
        """Record a failed API call"""
        self.total_requests += 1
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        # Deactivate on payment errors
        if "payment" in error_type.lower() or "delinquent" in error_type.lower():
            self.is_active = False
            logger.warning(f"🚫 Deactivating API key due to payment error: {error_type}")


class GroqAPIRotator:
    """
    Smart API key rotation system with failure tracking and recovery
    
    Features:
    - Round-robin selection of healthy keys
    - Automatic failure detection and key deactivation
    - Recovery monitoring and key reactivation
    - Health metrics and performance tracking
    - Cooldown periods for failed keys
    """
    
    def __init__(self, api_keys: List[str]):
        """
        Initialize rotator with API keys
        
        Args:
            api_keys: List of Groq API keys for rotation
        """
        if not api_keys:
            raise ValueError("At least one API key is required")
            
        # Initialize key status tracking
        self.key_statuses: Dict[str, APIKeyStatus] = {
            key: APIKeyStatus(key=key) for key in api_keys
        }
        
        self.current_index = 0
        self.total_requests = 0
        self.total_failures = 0
        
        logger.info(f"🔄 Groq API Rotator initialized with {len(api_keys)} keys")
        self._log_key_status()
    
    def get_next_healthy_key(self) -> Optional[str]:
        """
        Get the next healthy API key using round-robin selection
        
        Returns:
            API key string if available, None if all keys are unhealthy
        """
        healthy_keys = [key for key, status in self.key_statuses.items() if status.is_healthy]
        
        if not healthy_keys:
            logger.error("❌ No healthy API keys available!")
            self._attempt_recovery()
            # Try again after recovery attempt
            healthy_keys = [key for key, status in self.key_statuses.items() if status.is_healthy]
            
        if not healthy_keys:
            logger.critical("🚨 All API keys are unhealthy - system needs manual intervention")
            return None
            
        # Round-robin selection among healthy keys
        key = healthy_keys[self.current_index % len(healthy_keys)]
        self.current_index = (self.current_index + 1) % len(healthy_keys)
        
        logger.debug(f"🔑 Selected API key: {key[:8]}... (healthy keys: {len(healthy_keys)})")
        return key
    
    def record_success(self, api_key: str):
        """Record successful API call for key"""
        if api_key in self.key_statuses:
            self.key_statuses[api_key].record_success()
            self.total_requests += 1
            logger.debug(f"✅ Success recorded for key {api_key[:8]}...")
    
    def record_failure(self, api_key: str, error_message: str = ""):
        """Record failed API call for key with error classification"""
        if api_key in self.key_statuses:
            self.key_statuses[api_key].record_failure(error_message)
            self.total_requests += 1
            self.total_failures += 1
            
            logger.warning(f"❌ Failure recorded for key {api_key[:8]}...: {error_message}")
            
            # Log health status change
            if not self.key_statuses[api_key].is_healthy:
                logger.warning(f"🚫 Key {api_key[:8]}... marked as unhealthy")
                self._log_key_status()
    
    def get_health_report(self) -> Dict:
        """Get comprehensive health report of all keys"""
        healthy_count = sum(1 for status in self.key_statuses.values() if status.is_healthy)
        total_count = len(self.key_statuses)
        
        overall_success_rate = 0.0
        if self.total_requests > 0:
            overall_success_rate = ((self.total_requests - self.total_failures) / self.total_requests) * 100.0
        
        return {
            "total_keys": total_count,
            "healthy_keys": healthy_count,
            "unhealthy_keys": total_count - healthy_count,
            "overall_success_rate": round(overall_success_rate, 2),
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "key_details": [
                {
                    "key_preview": key[:8] + "...",
                    "is_healthy": status.is_healthy,
                    "is_active": status.is_active,
                    "success_rate": round(status.success_rate, 2),
                    "total_requests": status.total_requests,
                    "failure_count": status.failure_count,
                    "last_success": status.last_success_time.isoformat() if status.last_success_time else None,
                    "last_failure": status.last_failure_time.isoformat() if status.last_failure_time else None,
                }
                for key, status in self.key_statuses.items()
            ]
        }
    
    def _attempt_recovery(self):
        """Attempt to recover failed keys that may have healed"""
        current_time = datetime.utcnow()
        recovered_keys = []
        
        for key, status in self.key_statuses.items():
            if not status.is_healthy and status.last_failure_time:
                # Try to recover keys that failed more than 15 minutes ago
                time_since_failure = current_time - status.last_failure_time
                if time_since_failure > timedelta(minutes=15):
                    # Reset failure state to allow retry
                    status.is_active = True
                    recovered_keys.append(key)
        
        if recovered_keys:
            logger.info(f"🔄 Recovery attempt: reactivated {len(recovered_keys)} keys for retry")
    
    def _log_key_status(self):
        """Log current status of all keys"""
        healthy_keys = [key for key, status in self.key_statuses.items() if status.is_healthy]
        unhealthy_keys = [key for key, status in self.key_statuses.items() if not status.is_healthy]
        
        logger.info(f"📊 Key Status: {len(healthy_keys)} healthy, {len(unhealthy_keys)} unhealthy")
        
        if unhealthy_keys:
            for key in unhealthy_keys:
                status = self.key_statuses[key]
                logger.warning(f"   🚫 {key[:8]}... - Active: {status.is_active}, "
                             f"Success Rate: {status.success_rate:.1f}%, "
                             f"Last Failure: {status.last_failure_time}")
    
    def reset_key_status(self, api_key: str):
        """Reset status for a specific key (for manual recovery)"""
        if api_key in self.key_statuses:
            self.key_statuses[api_key] = APIKeyStatus(key=api_key)
            logger.info(f"🔄 Reset status for key {api_key[:8]}...")
    
    def deactivate_key(self, api_key: str, reason: str = "Manual deactivation"):
        """Manually deactivate a key"""
        if api_key in self.key_statuses:
            self.key_statuses[api_key].is_active = False
            logger.warning(f"🚫 Manually deactivated key {api_key[:8]}...: {reason}")
    
    @property
    def has_healthy_keys(self) -> bool:
        """Check if there are any healthy keys available"""
        return any(status.is_healthy for status in self.key_statuses.values())
    
    @property
    def healthy_key_count(self) -> int:
        """Get count of healthy keys"""
        return sum(1 for status in self.key_statuses.values() if status.is_healthy)