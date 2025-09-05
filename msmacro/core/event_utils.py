"""Event processing utilities for msmacro daemon."""
from typing import Dict, Any, List


def events_to_actions(events: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """Convert raw keyboard events to action format with press/duration."""
    actions: List[Dict[str, float]] = []
    down_time: Dict[int, float] = {}
    
    if not events:
        return actions
        
    # Sort events by timestamp
    sorted_events = sorted(events, key=lambda e: float(e.get("t", 0.0)))
    base_time = float(sorted_events[0].get("t", 0.0))
    
    for event in sorted_events:
        event_type = event.get("type", "").lower()
        usage = event.get("usage")
        timestamp = float(event.get("t", 0.0)) - base_time
        
        if usage is None:
            continue
            
        if event_type in ("down", "press"):
            down_time[usage] = timestamp
        elif event_type in ("up", "release"):
            if usage in down_time:
                press_time = down_time.pop(usage)
                duration = max(0.0, timestamp - press_time)
                actions.append({
                    "usage": usage,
                    "press": press_time, 
                    "dur": duration
                })
            else:
                # Unmatched release - treat as short tap
                actions.append({
                    "usage": usage,
                    "press": timestamp,
                    "dur": 0.010
                })
    
    # Handle any remaining pressed keys
    for usage, press_time in down_time.items():
        actions.append({
            "usage": usage,
            "press": press_time,
            "dur": 0.010
        })
    
    return sorted(actions, key=lambda a: a["press"])