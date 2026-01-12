"""
UASC-M2M Traffic Control Actions

Simulated traffic control system interface for the reference implementation.
In production, these would interface with actual traffic control hardware.
"""

import random
from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class TrafficSignal:
    """Represents a traffic signal."""
    signal_id: int
    zone: int
    timing: int = 30
    mode: str = 'normal'
    status: str = 'operational'


@dataclass
class TrafficZone:
    """Represents a traffic zone."""
    zone_id: int
    name: str
    signal_count: int
    congestion_level: float = 0.0
    signals: List[TrafficSignal] = field(default_factory=list)


class TrafficControlActions:
    """
    Traffic control system interface (simulated).

    Provides action handlers for:
    - Reading signal states
    - Updating signal timing
    - Emergency corridor clearing
    - Route optimization
    """

    def __init__(self):
        self.zones: Dict[int, TrafficZone] = {}
        self._init_mock_zones()

    def _init_mock_zones(self):
        """Initialize mock traffic zones and signals."""
        zone_names = {
            1: "Downtown Core",
            2: "Business District",
            3: "Residential North",
            4: "Residential South",
            5: "Industrial Zone",
            6: "Shopping District",
            7: "University Area",
            8: "Hospital District",
            9: "Airport Corridor",
            10: "Port Area"
        }

        for zone_id, name in zone_names.items():
            signal_count = random.randint(5, 15)
            signals = [
                TrafficSignal(
                    signal_id=i + 1,
                    zone=zone_id,
                    timing=random.choice([20, 25, 30, 35, 40])
                )
                for i in range(signal_count)
            ]

            self.zones[zone_id] = TrafficZone(
                zone_id=zone_id,
                name=name,
                signal_count=signal_count,
                congestion_level=random.uniform(0.1, 0.7),
                signals=signals
            )

    def get_signals(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get signals in a zone.

        Params:
            zone: Zone ID (int)

        Returns:
            zone: Zone ID
            signals: List of signal IDs
            current_timing: Average timing
            congestion: Current congestion level
        """
        zone_id = params.get('zone', 1)

        if zone_id not in self.zones:
            raise ValueError(f"Unknown zone: {zone_id}")

        zone = self.zones[zone_id]
        signal_ids = [s.signal_id for s in zone.signals]
        avg_timing = sum(s.timing for s in zone.signals) / len(zone.signals)

        return {
            'zone': zone_id,
            'zone_name': zone.name,
            'signals': signal_ids,
            'signal_count': len(signal_ids),
            'current_timing': int(avg_timing),
            'congestion': round(zone.congestion_level, 2)
        }

    def set_timing(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set signal timing for a zone.

        Params:
            signals: List of signal IDs or zone ID
            duration: New timing duration in seconds

        Returns:
            count: Number of signals updated
            new_timing: The applied timing
            status: Update status
        """
        signals = params.get('signals', [])
        duration = params.get('duration', 30)
        zone_id = params.get('zone')

        # If zone provided, get all signals in zone
        if zone_id and zone_id in self.zones:
            signals = [s.signal_id for s in self.zones[zone_id].signals]

        # Simulate updating signals
        count = len(signals) if isinstance(signals, list) else 0

        return {
            'count': count,
            'new_timing': duration,
            'status': 'updated',
            'message': f"Updated {count} signals to {duration}s timing"
        }

    def emergency_corridor(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clear emergency corridor through a zone.

        Sets all signals to priority mode for emergency vehicle passage.

        Params:
            zone: Zone ID
            vehicle_id: Emergency vehicle identifier

        Returns:
            signal_count: Number of signals affected
            vehicle_id: The vehicle ID
            corridor_status: Status of corridor
            route: Suggested route through zone
        """
        zone_id = params.get('zone', 1)
        vehicle_id = params.get('vehicle_id', 'unknown')

        if zone_id not in self.zones:
            raise ValueError(f"Unknown zone: {zone_id}")

        zone = self.zones[zone_id]

        # Set all signals in zone to emergency mode
        for signal in zone.signals:
            signal.mode = 'emergency'

        return {
            'signal_count': zone.signal_count,
            'vehicle_id': vehicle_id,
            'corridor_status': 'cleared',
            'zone_name': zone.name,
            'route': f"Emergency route through {zone.name} active",
            'estimated_clear_time_seconds': zone.signal_count * 5
        }

    def optimize_route(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize traffic flow through a zone.

        Analyzes current conditions and adjusts timing for optimal flow.

        Params:
            zone: Zone ID

        Returns:
            signal_count: Number of signals adjusted
            optimization: Type of optimization applied
            improvement: Estimated improvement percentage
        """
        zone_id = params.get('zone', 1)

        if zone_id not in self.zones:
            raise ValueError(f"Unknown zone: {zone_id}")

        zone = self.zones[zone_id]

        # Simulate optimization
        affected_signals = zone.signal_count // 2
        improvement = random.uniform(5, 15)

        return {
            'signal_count': affected_signals,
            'optimization': 'green_wave',
            'improvement_percent': round(improvement, 1),
            'zone_name': zone.name,
            'message': f"Optimized {affected_signals} signals for {improvement:.1f}% improvement"
        }

    def get_congestion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get current congestion level for a zone.

        Params:
            zone: Zone ID

        Returns:
            zone: Zone ID
            congestion: Congestion level (0-1)
            status: Congestion status text
        """
        zone_id = params.get('zone', 1)

        if zone_id not in self.zones:
            raise ValueError(f"Unknown zone: {zone_id}")

        zone = self.zones[zone_id]

        # Determine status based on congestion
        if zone.congestion_level < 0.3:
            status = 'light'
        elif zone.congestion_level < 0.6:
            status = 'moderate'
        elif zone.congestion_level < 0.8:
            status = 'heavy'
        else:
            status = 'severe'

        return {
            'zone': zone_id,
            'zone_name': zone.name,
            'congestion': round(zone.congestion_level, 2),
            'status': status
        }

    def reset_zone(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reset all signals in a zone to normal operation.

        Params:
            zone: Zone ID

        Returns:
            signal_count: Number of signals reset
            status: Reset status
        """
        zone_id = params.get('zone', 1)

        if zone_id not in self.zones:
            raise ValueError(f"Unknown zone: {zone_id}")

        zone = self.zones[zone_id]

        # Reset all signals to normal
        for signal in zone.signals:
            signal.mode = 'normal'
            signal.timing = 30

        return {
            'signal_count': zone.signal_count,
            'status': 'reset_complete',
            'zone_name': zone.name
        }


def register_traffic_actions(action_registry):
    """
    Register traffic control actions with an action registry.

    Args:
        action_registry: ActionRegistry instance to register with
    """
    tc = TrafficControlActions()

    action_registry.register('traffic.get_signals', tc.get_signals)
    action_registry.register('traffic.set_timing', tc.set_timing)
    action_registry.register('traffic.emergency_corridor', tc.emergency_corridor)
    action_registry.register('traffic.optimize_route', tc.optimize_route)
    action_registry.register('traffic.get_congestion', tc.get_congestion)
    action_registry.register('traffic.reset_zone', tc.reset_zone)
