"""
Skill injection system for CD skills during macro playback.
Handles skill cooldowns, trigger detection, and keystroke insertion.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..utils.keymap import name_to_usage
from .skills import SkillConfig

# HID usage IDs for arrow keys
ARROW_LEFT = 80
ARROW_RIGHT = 79


@dataclass
class SkillState:
    """Tracks state for an active skill."""
    config: SkillConfig
    last_used_time: float = 0.0
    is_casting: bool = False
    cast_end_time: float = 0.0

    # Cooldown + random delay tracking
    cooldown_ready_time: float = 0.0  # When base cooldown expires
    random_delay_duration: float = 0.0  # Random 1-30s delay after cooldown
    can_cast_after: float = 0.0  # cooldown_ready_time + random_delay_duration

    # Arrow key tracking
    last_arrow_direction: Optional[int] = None  # ARROW_LEFT or ARROW_RIGHT
    opposite_arrow_timer: float = 0.0  # Time when opposite arrow condition met
    opposite_arrow_delay: float = 0.0  # Random 0.5-1s delay
    arrow_condition_met: bool = False

    # After-key constraints tracking
    selected_trigger_key: Optional[int] = None  # Randomly selected from key1/2/3
    trigger_key_pressed: bool = False
    trigger_key_released_time: float = 0.0
    after_key_delay: float = 0.0  # after_keys_seconds ± 0.1s
    after_key_condition_met: bool = False

    def __post_init__(self):
        pass


class SkillInjector:
    """Manages skill injection during macro playback."""

    def __init__(self, active_skills: List[Dict[str, Any]]):
        self.skills: Dict[str, SkillState] = {}
        self.frozen_until: float = 0.0  # Global rotation freeze timestamp

        # Global arrow key tracking (shared across all skills)
        self.last_arrow_direction: Optional[int] = None
        self.last_arrow_time: float = 0.0

        # Initialize skill states
        for skill_data in active_skills:
            config = SkillConfig.from_dict(skill_data)
            state = SkillState(config=config)
            # Initialize cooldown system
            state.cooldown_ready_time = 0.0
            state.random_delay_duration = random.uniform(1.0, 30.0)
            state.can_cast_after = state.random_delay_duration
            self.skills[config.id] = state

    def _get_usage_from_name(self, key_name: str) -> Optional[int]:
        """Convert key name to HID usage ID."""
        if not key_name or not key_name.strip():
            return None
        return name_to_usage(key_name.strip())

    def _get_trigger_keys(self, config: SkillConfig) -> List[int]:
        """Get list of trigger key usage IDs for a skill configuration."""
        keys = []
        for key_name in [config.key1, config.key2, config.key3]:
            if key_name and key_name.strip():
                usage = self._get_usage_from_name(key_name)
                if usage:
                    keys.append(usage)
        return keys

    def update_arrow_key_tracking(self, pressed_keys: List[int], current_time: float) -> None:
        """Track arrow key presses for opposite arrow detection."""
        # Check if left or right arrow is currently pressed
        if ARROW_LEFT in pressed_keys:
            if self.last_arrow_direction == ARROW_RIGHT:
                # Opposite arrow detected! Update all skills
                for skill_state in self.skills.values():
                    if not skill_state.arrow_condition_met:
                        skill_state.opposite_arrow_timer = current_time
                        skill_state.opposite_arrow_delay = random.uniform(0.2, 0.45)
            self.last_arrow_direction = ARROW_LEFT
            self.last_arrow_time = current_time
        elif ARROW_RIGHT in pressed_keys:
            if self.last_arrow_direction == ARROW_LEFT:
                # Opposite arrow detected! Update all skills
                for skill_state in self.skills.values():
                    if not skill_state.arrow_condition_met:
                        skill_state.opposite_arrow_timer = current_time
                        skill_state.opposite_arrow_delay = random.uniform(0.2, 0.45)
            self.last_arrow_direction = ARROW_RIGHT
            self.last_arrow_time = current_time

    def update_skill_conditions(self, skill_id: str, pressed_keys: List[int], current_time: float) -> None:
        """Update all skill condition states."""
        if skill_id not in self.skills:
            return

        skill_state = self.skills[skill_id]
        config = skill_state.config

        # 1. Update cooldown + random delay
        if current_time >= skill_state.cooldown_ready_time and not skill_state.is_casting:
            # Cooldown has expired, check if we can cast after random delay
            if current_time >= skill_state.can_cast_after:
                # Ready to cast (cooldown + random delay both satisfied)
                pass

        # 2. Update arrow key condition
        if skill_state.opposite_arrow_timer > 0:
            if current_time >= skill_state.opposite_arrow_timer + skill_state.opposite_arrow_delay:
                skill_state.arrow_condition_met = True

        # 3. Update after-key constraints
        if config.after_key_constraints:
            # Select a random trigger key if not already selected
            if skill_state.selected_trigger_key is None:
                trigger_keys = self._get_trigger_keys(config)
                if trigger_keys:
                    skill_state.selected_trigger_key = random.choice(trigger_keys)
                    skill_state.after_key_delay = config.after_keys_seconds + random.uniform(-0.1, 0.1)

            # Check if selected trigger key is pressed
            if skill_state.selected_trigger_key and skill_state.selected_trigger_key in pressed_keys:
                skill_state.trigger_key_pressed = True
            elif skill_state.trigger_key_pressed:
                # Key was pressed and now released
                skill_state.trigger_key_released_time = current_time
                skill_state.trigger_key_pressed = False

            # Check if enough time has passed after key release
            if skill_state.trigger_key_released_time > 0:
                if current_time >= skill_state.trigger_key_released_time + skill_state.after_key_delay:
                    skill_state.after_key_condition_met = True

    def can_inject_skill(self, skill_id: str, pressed_keys: List[int], current_time: float) -> bool:
        """
        Check if ALL conditions are met for skill injection.

        Conditions:
        1. No other keys are pressed (only skill key or trigger keys)
        2. Cooldown + random delay (1-30s) has passed
        3. Opposite arrow keys were pressed with 0.5-1s delay
        4. If after_key_constraints: selected key was pressed, released, and delay passed
        5. Skill is not currently casting
        """
        if skill_id not in self.skills:
            return False

        skill_state = self.skills[skill_id]
        config = skill_state.config

        # Skip if not selected
        if not config.is_selected:
            return False

        # Skip if casting
        if skill_state.is_casting:
            return False

        # Condition 1: No other keys should be pressed
        # For now, we check this at injection time in the player

        # Condition 2: Cooldown + random delay
        if current_time < skill_state.can_cast_after:
            return False

        # Condition 3: Arrow key opposite detection
        if not skill_state.arrow_condition_met:
            return False

        # Condition 4: After-key constraints
        if config.after_key_constraints:
            if not skill_state.after_key_condition_met:
                return False

        return True

    def should_freeze_rotation(self, current_time: float) -> bool:
        """Check if rotation should be frozen due to skill casting."""
        return current_time < self.frozen_until

    def cast_skill(self, skill_id: str, current_time: float) -> Optional[Dict[str, Any]]:
        """
        Cast a skill and return casting information.

        Returns:
            Dict with skill usage, pause times, or None if cannot cast
        """
        if skill_id not in self.skills:
            return None

        skill_state = self.skills[skill_id]
        config = skill_state.config

        skill_press = random.uniform(0.1, 0.15)

        # Get skill keystroke
        skill_usage = self._get_usage_from_name(config.keystroke)
        if not skill_usage:
            return None

        # Mark as casting
        skill_state.is_casting = True
        skill_state.last_used_time = current_time

        # Reset cooldown timer
        skill_state.cooldown_ready_time = current_time + config.cooldown
        skill_state.random_delay_duration = random.uniform(1.0, 30.0)
        skill_state.can_cast_after = skill_state.cooldown_ready_time + skill_state.random_delay_duration

        # Reset arrow condition
        skill_state.arrow_condition_met = False
        skill_state.opposite_arrow_timer = 0.0

        # Reset after-key condition
        skill_state.after_key_condition_met = False
        skill_state.selected_trigger_key = None
        skill_state.trigger_key_released_time = 0.0

        # Calculate frozen rotation pauses if enabled
        if config.frozen_rotation_during_casting:
            pre_pause = random.uniform(0.5, 0.7)
            post_pause = random.uniform(0.5, 0.7)
            total_cast_time = pre_pause + skill_press + post_pause  # 0.1s for key press
            skill_state.cast_end_time = current_time + total_cast_time
            self.frozen_until = skill_state.cast_end_time

            return {
                "usage": skill_usage,
                "pre_pause": pre_pause,
                "post_pause": post_pause,
                "press_duration": skill_press,
            }
        else:
            skill_state.cast_end_time = current_time + 0.1
            return {
                "usage": skill_usage,
                "pre_pause": 0.0,
                "post_pause": 0.0,
                "press_duration": skill_press,
            }

    def update_casting_state(self, current_time: float) -> None:
        """Update casting states for all skills."""
        for skill_state in self.skills.values():
            if skill_state.is_casting and current_time >= skill_state.cast_end_time:
                skill_state.is_casting = False

    def check_and_inject_skills(
        self,
        pressed_keys: List[int],
        current_time: float
    ) -> Optional[Dict[str, Any]]:
        """
        Check all skills and return injection info if any skill should be cast.
        Only injects if NO other keys are pressed.

        Returns:
            Skill cast info dict or None
        """
        # Update arrow key tracking
        self.update_arrow_key_tracking(pressed_keys, current_time)

        # Update casting states
        self.update_casting_state(current_time)

        # Update all skill conditions
        for skill_id in self.skills.keys():
            self.update_skill_conditions(skill_id, pressed_keys, current_time)

        # Check each skill for injection
        for skill_id in self.skills.keys():
            if not self.can_inject_skill(skill_id, pressed_keys, current_time):
                continue

            # Additional check: only inject if no other keys are pressed
            # Allow injection only if no keys are pressed
            if len(pressed_keys) == 0:
                return self.cast_skill(skill_id, current_time)

        return None


__all__ = ["SkillInjector", "SkillState"]