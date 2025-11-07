"""
System information command handler for msmacro daemon.

Provides real-time system performance metrics for debugging on Raspberry Pi.
"""

from typing import Dict, Any
import psutil
import platform


class SystemCommandHandler:
    """Handler for system information IPC commands."""

    def __init__(self, daemon):
        """
        Initialize the system command handler.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

    async def system_stats(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get current system performance metrics.

        Returns:
            Dictionary containing:
                - cpu_percent: Overall CPU usage percentage
                - cpu_count: Number of CPU cores
                - memory_percent: RAM usage percentage
                - memory_available_mb: Available RAM in MB
                - memory_total_mb: Total RAM in MB
                - disk_percent: Disk usage percentage
                - disk_free_gb: Free disk space in GB
                - temperature: CPU temperature in Celsius (if available on Pi)
                - uptime_seconds: System uptime in seconds
        """
        try:
            # CPU stats
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()

            # Memory stats
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_mb = memory.available / (1024 * 1024)
            memory_total_mb = memory.total / (1024 * 1024)

            # Disk stats
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free_gb = disk.free / (1024 * 1024 * 1024)

            # Uptime
            boot_time = psutil.boot_time()
            import time
            uptime_seconds = time.time() - boot_time

            # CPU Temperature (Raspberry Pi specific)
            temperature = None
            try:
                if platform.system() == 'Linux':
                    # Try to read from Raspberry Pi thermal zone
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        temperature = float(f.read().strip()) / 1000.0
            except Exception:
                pass

            return {
                "cpu_percent": round(cpu_percent, 1),
                "cpu_count": cpu_count,
                "memory_percent": round(memory_percent, 1),
                "memory_available_mb": round(memory_available_mb, 1),
                "memory_total_mb": round(memory_total_mb, 1),
                "disk_percent": round(disk_percent, 1),
                "disk_free_gb": round(disk_free_gb, 2),
                "temperature": round(temperature, 1) if temperature else None,
                "uptime_seconds": int(uptime_seconds),
            }

        except Exception as e:
            return {
                "error": f"Failed to get system stats: {str(e)}",
                "cpu_percent": 0,
                "cpu_count": 0,
                "memory_percent": 0,
                "memory_available_mb": 0,
                "memory_total_mb": 0,
                "disk_percent": 0,
                "disk_free_gb": 0,
                "temperature": None,
                "uptime_seconds": 0,
            }
