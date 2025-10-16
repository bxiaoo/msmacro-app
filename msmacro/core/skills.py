"""
Skills management system for CD skills functionality.
Handles CRUD operations for skill configurations stored as JSON files.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class SkillConfig:
    """Configuration for a CD skill."""
    id: str
    name: str
    keystroke: str
    cooldown: float
    key_replacement: bool = False
    replace_rate: float = 0.7
    frozen_rotation_during_casting: bool = False
    is_selected: bool = False
    # Group and ordering fields
    order: int = 0
    group_id: Optional[str] = None
    delay_after: float = 0.0  # Delay in seconds after this skill casts (for group members)
    # Frontend-only UI state (not persisted to disk)
    variant: str = "cd skill"
    is_open: bool = False
    is_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (frontend format with camelCase)."""
        return {
            "id": self.id,
            "name": self.name,
            "keystroke": self.keystroke,
            "cooldown": self.cooldown,
            "keyReplacement": self.key_replacement,
            "replaceRate": self.replace_rate,
            "frozenRotationDuringCasting": self.frozen_rotation_during_casting,
            "isSelected": self.is_selected,
            # Group and ordering
            "order": self.order,
            "groupId": self.group_id,
            "delayAfter": self.delay_after,
            # Frontend UI state
            "variant": self.variant,
            "isOpen": self.is_open,
            "isEnabled": self.is_enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillConfig":
        """Create SkillConfig from dictionary (accepts both camelCase and snake_case)."""
        # Ensure ID exists
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        # Handle legacy field names if any
        if "cooldown_seconds" in data:
            data["cooldown"] = data.pop("cooldown_seconds")

        # Convert camelCase from frontend to snake_case for dataclass
        normalized = {}
        for k, v in data.items():
            # Map camelCase to snake_case
            if k == "keyReplacement":
                normalized["key_replacement"] = v
            elif k == "replaceRate":
                normalized["replace_rate"] = v
            elif k == "frozenRotationDuringCasting":
                normalized["frozen_rotation_during_casting"] = v
            elif k == "isSelected":
                normalized["is_selected"] = v
            elif k == "isOpen":
                normalized["is_open"] = v
            elif k == "isEnabled":
                normalized["is_enabled"] = v
            elif k == "groupId":
                normalized["group_id"] = v
            elif k == "delayAfter":
                normalized["delay_after"] = v
            # Legacy field migration - ignore old fields
            elif k in ("afterKeyConstraints", "key1", "key2", "key3", "afterKeysSeconds"):
                continue  # Skip legacy fields
            else:
                normalized[k] = v

        return cls(**{k: v for k, v in normalized.items() if k in cls.__dataclass_fields__})


class SkillManager:
    """Manages skill configurations stored as JSON files."""

    def __init__(self, skills_dir: Union[str, Path]):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def _skill_file_path(self, skill_id: str) -> Path:
        """Get the file path for a skill by ID."""
        # Sanitize skill_id to be filesystem-safe
        safe_id = "".join(c for c in skill_id if c.isalnum() or c in "-_")
        return self.skills_dir / f"{safe_id}.json"

    def list_skills(self) -> List[SkillConfig]:
        """List all skill configurations."""
        skills = []

        for skill_file in self.skills_dir.glob("*.json"):
            try:
                data = json.loads(skill_file.read_text(encoding="utf-8"))
                skill = SkillConfig.from_dict(data)
                skills.append(skill)
            except Exception as e:
                # Log error but continue with other skills
                print(f"Warning: Failed to load skill from {skill_file}: {e}")
                continue

        # Sort by name for consistent ordering
        skills.sort(key=lambda s: s.name.lower())
        return skills

    def get_skill(self, skill_id: str) -> Optional[SkillConfig]:
        """Get a specific skill by ID."""
        skill_file = self._skill_file_path(skill_id)

        if not skill_file.exists():
            return None

        try:
            data = json.loads(skill_file.read_text(encoding="utf-8"))
            return SkillConfig.from_dict(data)
        except Exception:
            return None

    def save_skill(self, skill: SkillConfig) -> SkillConfig:
        """Save a skill configuration."""
        # Ensure skill has an ID
        if not skill.id:
            skill.id = str(uuid.uuid4())

        skill_file = self._skill_file_path(skill.id)
        skill_file.write_text(
            json.dumps(skill.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        return skill

    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Optional[SkillConfig]:
        """Update an existing skill with new data."""
        existing_skill = self.get_skill(skill_id)
        if not existing_skill:
            return None

        # Apply updates
        skill_dict = existing_skill.to_dict()
        skill_dict.update(updates)

        # Create updated skill
        updated_skill = SkillConfig.from_dict(skill_dict)
        return self.save_skill(updated_skill)

    def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill configuration."""
        skill_file = self._skill_file_path(skill_id)

        if not skill_file.exists():
            return False

        try:
            skill_file.unlink()
            return True
        except Exception:
            return False

    def get_selected_skills(self) -> List[SkillConfig]:
        """Get all skills marked as selected for active use."""
        all_skills = self.list_skills()
        return [skill for skill in all_skills if skill.is_selected]

    def create_skill_from_frontend_data(self, data: Dict[str, Any]) -> SkillConfig:
        """Create a SkillConfig from frontend skill data format."""
        # Map frontend field names to SkillConfig field names
        skill_data = {
            "id": data.get("id") or str(uuid.uuid4()),
            "name": data.get("name") or data.get("skillKey", ""),
            "keystroke": data.get("skillKey") or data.get("keystroke", ""),
            "cooldown": float(data.get("cooldown", 120)),
            "key_replacement": bool(data.get("keyReplacement", False)),
            "replace_rate": float(data.get("replaceRate", 0.7)),
            "frozen_rotation_during_casting": bool(data.get("frozenRotationDuringCasting", False)),
            "is_selected": bool(data.get("isSelected", False)),
        }

        return SkillConfig.from_dict(skill_data)


__all__ = ["SkillConfig", "SkillManager"]