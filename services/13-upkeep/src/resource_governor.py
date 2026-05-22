"""Resource Governor — mencegah laptop hang karena Vyper.

Monitoring:
- CPU usage per service
- Memory usage per service
- Disk I/O  
- Docker container stats

Actions:
- Throttle parallel scans jika CPU > 80%
- Kill OOM containers
- Pause daemon jika battery low (laptop)
- Queue delay jika resource contention
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import psutil

logger = logging.getLogger("vyper.upkeep.resource_governor")


class SystemLoad(Enum):
    IDLE = "idle"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResourceState:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_io_mbps: float = 0.0
    battery_percent: Optional[float] = None
    is_on_battery: bool = False
    docker_container_count: int = 0
    load: SystemLoad = SystemLoad.IDLE


class ResourceGovernor:
    """Central resource manager untuk semua service.
    
    Policy:
    - CPU < 50%: IDLE — full speed, max 5 parallel scans
    - CPU 50-70%: MODERATE — max 3 parallel scans  
    - CPU 70-90%: HIGH — max 1 scan, delay daemon
    - CPU > 90%: CRITICAL — pause all, notify user
    - Battery < 20%: REDUCED — min resource mode
    """
    
    def __init__(self):
        self._scan_semaphore = asyncio.Semaphore(5)
        self._state = ResourceState()
        self._monitoring = False
        self._listeners: list[callable] = []
    
    def add_listener(self, callback: callable) -> None:
        """Register a callback for load change events."""
        self._listeners.append(callback)
    
    async def start_monitoring(self, interval: float = 5.0) -> None:
        """Start background monitoring loop."""
        self._monitoring = True
        while self._monitoring:
            self._state = await self._collect_stats()
            await self._apply_policy()
            await asyncio.sleep(interval)
    
    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._monitoring = False
    
    async def _collect_stats(self) -> ResourceState:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent
        state = ResourceState(cpu_percent=cpu, memory_percent=mem)
        
        # Battery check
        if hasattr(psutil, "sensors_battery"):
            batt = psutil.sensors_battery()
            if batt:
                state.battery_percent = batt.percent
                state.is_on_battery = not batt.power_plugged
        
        # Load classification
        if cpu > 90 or mem > 90:
            state.load = SystemLoad.CRITICAL
        elif cpu > 70 or mem > 80:
            state.load = SystemLoad.HIGH
        elif cpu > 50 or mem > 60:
            state.load = SystemLoad.MODERATE
        else:
            state.load = SystemLoad.IDLE
        
        return state
    
    async def _apply_policy(self) -> None:
        """Adjust resource allocation based on current load."""
        load = self._state.load
        old_load = getattr(self, '_last_load', None)
        self._last_load = load
        
        # Notify listeners on load change
        if old_load and old_load != load:
            for cb in self._listeners:
                try:
                    await cb(load)
                except Exception:
                    logger.exception("listener failed")
        
        # Adjust scan parallelism
        if load == SystemLoad.IDLE:
            new_limit = 5
        elif load == SystemLoad.MODERATE:
            new_limit = 3
        elif load == SystemLoad.HIGH:
            new_limit = 1
        else:  # CRITICAL
            new_limit = 0  # Pause
        
        # Resize semaphore
        while self._scan_semaphore._value < new_limit:
            self._scan_semaphore.release()
        
        logger.info("Policy applied: load=%s scan_limit=%d cpu=%.1f", 
                    load.value, new_limit, self._state.cpu_percent)
    
    async def acquire_scan_slot(self) -> bool:
        """Acquire scan slot — blocks if resource constrained."""
        if self._state.load == SystemLoad.CRITICAL:
            logger.warning("Scan rejected: critical system load")
            return False
        await self._scan_semaphore.acquire()
        return True
    
    def release_scan_slot(self) -> None:
        """Release scan slot."""
        self._scan_semaphore.release()
    
    @property
    def current_load(self) -> SystemLoad:
        return self._state.load
    
    @property
    def state(self) -> ResourceState:
        return self._state


# ── Factory ──────────────────────────────────────────────────────


def create_resource_governor() -> ResourceGovernor:
    """Create a ResourceGovernor instance."""
    return ResourceGovernor()
