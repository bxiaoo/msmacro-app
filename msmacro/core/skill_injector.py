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

# HID usage IDs for arrow keys and special keys
ARROW_LEFT = 80
ARROW_RIGHT = 79
SPACE_KEY = 44


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
    opposite_arrow_delay: float = 0.0  # Random 0.3-0.75s delay
    arrow_condition_met: bool = False

    # Key replacement tracking (new logic)
    space_key_released_time: float = 0.0  # When space key was released
    space_delay: float = 0.0  # Random 0.33-0.5s delay after space
    use_replacement_mode: bool = False  # True=replace ignore_key, False=after-space
    replacement_ready: bool = False  # Condition 3: Replacement logic passed

    # Cascading condition state flags (new prioritized flow)
    cooldown_passed: bool = False  # Condition 1: Cooldown + random delay passed
    arrow_ready: bool = False  # Condition 2: Opposite arrow + delay passed

    # Group casting state (new for sequential group casting)
    group_delay_end_time: float = 0.0  # When this skill can cast after previous group member
    waiting_for_previous_skill: bool = False  # True if waiting for previous skill in group

    # Group completion tracking (for metrics/logging)
    group_completion_time: float = 0.0  # When the group last completed a full cycle

    # NEW: Group restart logic
    group_first_cast: bool = True  # True if group has never cast before (allows immediate start)
    group_restart_time: float = 0.0  # When group can restart after completion (last_skill_cooldown + random)

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

        # Group management (new for sequential group casting)
        self.skill_groups: Dict[str, List[str]] = {}  # group_id -> [skill_ids in order]
        self.group_casting_state: Dict[str, int] = {}  # group_id -> index of next skill to cast

        # Initialize skill states
        for skill_data in active_skills:
            config = SkillConfig.from_dict(skill_data)
            state = SkillState(config=config)
            # Initialize cooldown system
            state.cooldown_ready_time = 0.0
            state.random_delay_duration = random.uniform(1.0, 30.0)
            state.can_cast_after = state.random_delay_duration
            self.skills[config.id] = state

        # Build group structure
        self._build_skill_groups(active_skills)

    def _get_usage_from_name(self, key_name: str) -> Optional[int]:
        """Convert key name to HID usage ID."""
        if not key_name or not key_name.strip():
            return None
        return name_to_usage(key_name.strip())

    def _build_skill_groups(self, active_skills: List[Dict[str, Any]]) -> None:
        """
        Organize skills by group_id and order.
        Builds self.skill_groups mapping: group_id -> [skill_ids in order]
        """
        # Sort skills by order
        sorted_skills = sorted(active_skills, key=lambda s: s.get('order', 0))

        for skill_data in sorted_skills:
            # Handle both snake_case and camelCase
            group_id = skill_data.get('group_id') or skill_data.get('groupId')
            skill_id = skill_data.get('id')

            if group_id and skill_id:
                if group_id not in self.skill_groups:
                    self.skill_groups[group_id] = []
                    self.group_casting_state[group_id] = 0  # Start at first skill
                self.skill_groups[group_id].append(skill_id)


    def update_arrow_key_tracking(self, pressed_keys: List[int], current_time: float) -> None:
        """Track arrow key presses for opposite arrow detection."""
        # Check if left or right arrow is currently pressed
        if ARROW_LEFT in pressed_keys:
            if self.last_arrow_direction == ARROW_RIGHT:
                # Opposite arrow detected! Update all skills
                for skill_state in self.skills.values():
                    # Only update if cooldown passed but not yet casting
                    if skill_state.cooldown_passed and not skill_state.is_casting:
                        # Reset timer - recalculate delay (allows reset if opposite pressed again)
                        skill_state.opposite_arrow_timer = current_time
                        skill_state.opposite_arrow_delay = random.uniform(
                            skill_state.config.cast_position,
                            skill_state.config.cast_position + 0.2
                        )
                        skill_state.arrow_ready = False  # Reset ready flag
            self.last_arrow_direction = ARROW_LEFT
            self.last_arrow_time = current_time
        elif ARROW_RIGHT in pressed_keys:
            if self.last_arrow_direction == ARROW_LEFT:
                # Opposite arrow detected! Update all skills
                for skill_state in self.skills.values():
                    # Only update if cooldown passed but not yet casting
                    if skill_state.cooldown_passed and not skill_state.is_casting:
                        # Reset timer - recalculate delay (allows reset if opposite pressed again)
                        skill_state.opposite_arrow_timer = current_time
                        skill_state.opposite_arrow_delay = random.uniform(
                            skill_state.config.cast_position,
                            skill_state.config.cast_position + 0.2
                        )
                        skill_state.arrow_ready = False  # Reset ready flag
            self.last_arrow_direction = ARROW_RIGHT
            self.last_arrow_time = current_time

    def update_skill_conditions(self, skill_id: str, pressed_keys: List[int], current_time: float, ignore_keys: Optional[List[int]] = None) -> None:
        """
        Update skill condition states with PRIORITIZED CASCADE LOGIC.

        Conditions are checked in strict order:
        1. Cooldown + random delay (PRIMARY - blocks all others)
        2. Opposite arrow keys + delay (only if cooldown passed)
        3. Key replacement logic (only if arrow ready and key_replacement enabled)
        4. No other keys pressed (checked in check_and_inject_skills)
        """
        if skill_id not in self.skills:
            return

        skill_state = self.skills[skill_id]
        config = skill_state.config

        # ===== CONDITION 1: Cooldown + Random Delay (PRIMARY) =====
        # This MUST pass before any other conditions are evaluated
        # NEW: Grouped skills bypass individual cooldown logic
        if config.group_id:
            # Grouped skills always pass cooldown condition (group-level timing handled separately)
            skill_state.cooldown_passed = True
        elif current_time >= skill_state.can_cast_after and not skill_state.is_casting:
            # Solo skills use normal cooldown logic
            skill_state.cooldown_passed = True
        else:
            # Cooldown not ready - don't process other conditions yet
            # Reset downstream conditions
            skill_state.cooldown_passed = False
            skill_state.arrow_ready = False
            skill_state.replacement_ready = False
            return

        # ===== CONDITION 2: Opposite Arrow Keys + Delay =====
        # Only evaluated if cooldown passed
        if skill_state.cooldown_passed:
            # Check if opposite arrow timer started
            if skill_state.opposite_arrow_timer > 0:
                # Check if delay elapsed
                if current_time >= skill_state.opposite_arrow_timer + skill_state.opposite_arrow_delay:
                    skill_state.arrow_ready = True
                    skill_state.arrow_condition_met = True  # Keep for compatibility

            # If arrow not ready, don't process next condition
            if not skill_state.arrow_ready:
                skill_state.replacement_ready = False
                return

        # ===== CONDITION 3: Key Replacement Logic =====
        # Only evaluated if arrow ready
        if config.key_replacement and skill_state.arrow_ready:
            # Determine replacement mode on first evaluation after arrow ready
            if not skill_state.use_replacement_mode and skill_state.space_key_released_time == 0:
                # Randomly decide: replace_rate% = replacement, (1-replace_rate)% = after-space
                skill_state.use_replacement_mode = random.random() < config.replace_rate

                if not skill_state.use_replacement_mode:
                    # After-space mode: set up space key delay (0.33-0.5s)
                    skill_state.space_delay = random.uniform(0.33, 0.5)

            if skill_state.use_replacement_mode:
                # Replacement mode: skill replaces ignore_key (ready immediately if ignore_keys available)
                if ignore_keys and len(ignore_keys) > 0:
                    skill_state.replacement_ready = True
                else:
                    # No ignore_keys configured, can't use replacement mode
                    skill_state.replacement_ready = False
            else:
                # After-space mode: wait for space key release + delay
                # Track space key
                space_pressed = SPACE_KEY in pressed_keys

                if space_pressed:
                    # Space is currently pressed (not released yet)
                    pass
                elif skill_state.space_key_released_time == 0:
                    # Space was released (first time detection)
                    # Check if space was pressed before (simple heuristic: assume it was)
                    skill_state.space_key_released_time = current_time

                # Check if enough time passed after space release
                if skill_state.space_key_released_time > 0:
                    if current_time >= skill_state.space_key_released_time + skill_state.space_delay:
                        skill_state.replacement_ready = True
        else:
            # No key replacement - auto-pass this condition (original behavior)
            skill_state.replacement_ready = True

    def _check_group_casting_order(self, skill_id: str, current_time: float) -> bool:
        """
        Check if this skill can cast based on group order (NEW LOGIC).

        Returns True if:
        - Skill is not in a group (solo skill) - always pass
        - Skill is first in group:
          * If never cast before (group_first_cast=True): Return True immediately
          * If cast before: Check if current_time >= group_restart_time
        - Skill is subsequent in group:
          * Previous skill must have cast (last_used_time > 0)
          * Wait for: previous_last_used_time + previous_delay_after + random(1-5s)

        Key changes:
        - Individual cooldowns ignored for grouped skills
        - First cast happens immediately (no cooldown wait)
        - Group restarts after: last_skill_cooldown + random(1-5s)
        - Within-group timing: delay_after + random(1-5s)
        """
        if skill_id not in self.skills:
            return False

        skill_state = self.skills[skill_id]
        config = skill_state.config

        # Solo skill (not in a group) - always pass
        if not config.group_id:
            return True

        # Get group members
        group_members = self.skill_groups.get(config.group_id, [])
        if not group_members:
            return True  # Group doesn't exist, treat as solo

        # Find this skill's index in the group
        try:
            skill_index = group_members.index(skill_id)
        except ValueError:
            return True  # Skill not in group list, treat as solo

        # Get current group state
        current_index = self.group_casting_state.get(config.group_id, 0)

        # Must be the next skill in sequence
        if current_index != skill_index:
            return False

        # ===== FIRST SKILL IN GROUP (index 0) =====
        if skill_index == 0:
            # Check if this is the first time group is casting
            if skill_state.group_first_cast:
                # First cast ever - start immediately (no cooldown wait)
                return True
            else:
                # Group has cast before - wait for restart timer
                # (set by last skill: last_skill_cooldown + random(1-5s))
                return current_time >= skill_state.group_restart_time

        # ===== SUBSEQUENT SKILLS IN GROUP =====
        previous_skill_id = group_members[skill_index - 1]
        previous_state = self.skills.get(previous_skill_id)

        if not previous_state:
            return False  # Previous skill doesn't exist

        # Check if previous skill has been cast
        if previous_state.last_used_time == 0.0:
            return False  # Previous skill never cast yet

        # Calculate when this skill can cast (only once)
        if skill_state.group_delay_end_time == 0.0:
            random_delay = random.uniform(1.0, 5.0)
            skill_state.group_delay_end_time = (
                previous_state.last_used_time +      # When previous actually cast
                previous_state.config.delay_after +  # Configured delay
                random_delay                          # Random 1-5s
            )

        # Check if enough time has passed
        return current_time >= skill_state.group_delay_end_time

    def can_inject_skill(self, skill_id: str, pressed_keys: List[int], current_time: float) -> bool:
        """
        Check if ALL cascaded conditions are met for skill injection.

        This method simply checks the condition flags that were set by update_skill_conditions().
        The cascade logic ensures conditions are evaluated in priority order:
        1. Cooldown + random delay (PRIMARY)
        2. Opposite arrow keys + delay
        3. Key replacement logic (if configured)
        4. No other keys pressed (checked in check_and_inject_skills)
        """
        if skill_id not in self.skills:
            return False

        skill_state = self.skills[skill_id]
        config = skill_state.config

        # Skip if not selected or currently casting
        if not config.is_selected or skill_state.is_casting:
            return False

        # Check cascaded condition flags in priority order
        if not skill_state.cooldown_passed:
            return False

        if not skill_state.arrow_ready:
            return False

        if not skill_state.replacement_ready:
            return False

        # All prior conditions passed
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

        # Reset all cascading condition flags
        skill_state.cooldown_passed = False
        skill_state.arrow_ready = False
        skill_state.replacement_ready = False

        # Reset arrow condition (legacy compatibility)
        skill_state.arrow_condition_met = False
        skill_state.opposite_arrow_timer = 0.0

        # Reset key replacement tracking
        skill_state.space_key_released_time = 0.0
        skill_state.space_delay = 0.0
        skill_state.use_replacement_mode = False

        # NEW: Update group casting state
        if config.group_id:
            group_members = self.skill_groups.get(config.group_id, [])
            try:
                skill_index = group_members.index(skill_id)
                is_last_skill = (skill_index == len(group_members) - 1)

                if is_last_skill:
                    # Last skill in group - calculate restart time and reset to start
                    completion_time = current_time

                    # Calculate group restart time: last_skill_cooldown + random(1-5s)
                    restart_random_delay = random.uniform(1.0, 5.0)
                    group_restart_time = current_time + config.cooldown + restart_random_delay

                    # Update ALL group members
                    for member_id in group_members:
                        member_state = self.skills.get(member_id)
                        if member_state:
                            member_state.group_completion_time = completion_time
                            member_state.group_restart_time = group_restart_time
                            member_state.group_first_cast = False  # No longer first cast

                    # Reset group to first skill - will restart when group_restart_time passes
                    self.group_casting_state[config.group_id] = 0
                else:
                    # Not last skill - advance to next skill in group
                    self.group_casting_state[config.group_id] = skill_index + 1

            except ValueError:
                pass  # Skill not in group list

        # Reset group delay for this skill (will be recalculated on next cast attempt)
        skill_state.group_delay_end_time = 0.0

        # Calculate pauses
        # General post-casting delay (always applied for human-like behavior)
        general_post_delay = random.uniform(config.skill_delay, config.skill_delay + 0.2)

        if config.frozen_rotation_during_casting:
            # Frozen rotation: add extra pauses before and after
            pre_pause = random.uniform(0.5, 0.7)
            post_pause = random.uniform(0.5, 0.7)
            total_cast_time = pre_pause + skill_press + post_pause + general_post_delay
            skill_state.cast_end_time = current_time + total_cast_time
            self.frozen_until = skill_state.cast_end_time

            return {
                "usage": skill_usage,
                "pre_pause": pre_pause,
                "post_pause": post_pause + general_post_delay,  # Combined post pauses
                "press_duration": skill_press,
            }
        else:
            # Normal casting: only general post delay
            total_cast_time = skill_press + general_post_delay
            skill_state.cast_end_time = current_time + total_cast_time

            return {
                "usage": skill_usage,
                "pre_pause": 0.0,
                "post_pause": general_post_delay,  # General post-casting delay
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
        current_time: float,
        ignore_keys: Optional[List[int]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check all skills and return injection info if any skill should be cast.
        Only injects if NO other keys are pressed (or in replacement mode).

        Args:
            pressed_keys: Currently pressed HID usage IDs
            current_time: Current time
            ignore_keys: List of HID usage IDs that can be replaced by skills

        Returns:
            Skill cast info dict or None
        """
        # Update arrow key tracking
        self.update_arrow_key_tracking(pressed_keys, current_time)

        # Update casting states
        self.update_casting_state(current_time)

        # Update all skill conditions (pass ignore_keys for replacement logic)
        for skill_id in self.skills.keys():
            self.update_skill_conditions(skill_id, pressed_keys, current_time, ignore_keys)

        # Check each skill for injection
        for skill_id in self.skills.keys():
            if not self.can_inject_skill(skill_id, pressed_keys, current_time):
                continue

            # NEW: Check group casting order (additional cascade condition)
            if not self._check_group_casting_order(skill_id, current_time):
                continue

            skill_state = self.skills[skill_id]

            # If in replacement mode, can inject anytime (skill will replace ignore_key)
            if skill_state.use_replacement_mode:
                return self.cast_skill(skill_id, current_time)

            # Otherwise, only inject if no other keys are pressed
            if len(pressed_keys) == 0:
                return self.cast_skill(skill_id, current_time)

        return None


__all__ = ["SkillInjector", "SkillState"]