"""
Skills management command handlers for msmacro daemon.

Handles IPC commands for CD skills CRUD operations including
listing, creating, updating, deleting, and reordering skills.
"""

from typing import Dict, Any


class SkillsCommandHandler:
    """Handler for skills management IPC commands."""

    def __init__(self, daemon):
        """
        Initialize the skills command handler.

        Args:
            daemon: Reference to the parent MacroDaemon instance
        """
        self.daemon = daemon

    async def list_skills(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all available CD skills.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "skills" key containing list of skill dictionaries
        """
        skills = self.daemon.skills_manager.list_skills()
        return {"skills": [skill.to_dict() for skill in skills]}

    async def save_skill(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new CD skill.

        Args:
            msg: IPC message containing:
                - skill_data: Dictionary with skill configuration

        Returns:
            Dictionary with "skill" key containing the saved skill data
                and "saved" key set to True

        Raises:
            RuntimeError: If skill_data is missing
        """
        skill_data = msg.get("skill_data")
        if not skill_data:
            raise RuntimeError("missing skill_data")

        skill = self.daemon.skills_manager.create_skill_from_frontend_data(skill_data)
        saved_skill = self.daemon.skills_manager.save_skill(skill)

        return {"skill": saved_skill.to_dict(), "saved": True}

    async def update_skill(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing CD skill.

        Args:
            msg: IPC message containing:
                - skill_id: ID of skill to update
                - skill_data: Dictionary with updated skill configuration

        Returns:
            Dictionary with "skill" key containing the updated skill data
                and "updated" key set to True

        Raises:
            RuntimeError: If skill_id/skill_data missing or skill not found
        """
        skill_id = msg.get("skill_id")
        skill_data = msg.get("skill_data")

        if not skill_id or not skill_data:
            raise RuntimeError("missing skill_id or skill_data")

        updated_skill = self.daemon.skills_manager.update_skill(skill_id, skill_data)
        if not updated_skill:
            raise RuntimeError(f"skill not found: {skill_id}")

        return {"skill": updated_skill.to_dict(), "updated": True}

    async def delete_skill(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a CD skill.

        Args:
            msg: IPC message containing:
                - skill_id: ID of skill to delete

        Returns:
            Dictionary with "deleted" key set to True and "skill_id"

        Raises:
            RuntimeError: If skill_id missing or skill not found
        """
        skill_id = msg.get("skill_id")
        if not skill_id:
            raise RuntimeError("missing skill_id")

        success = self.daemon.skills_manager.delete_skill(skill_id)
        if not success:
            raise RuntimeError(f"skill not found: {skill_id}")

        return {"deleted": True, "skill_id": skill_id}

    async def get_selected_skills(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get all currently selected (active) CD skills.

        Args:
            msg: IPC message (unused)

        Returns:
            Dictionary with "skills" key containing list of selected skill dictionaries
        """
        selected_skills = self.daemon.skills_manager.get_selected_skills()
        return {"skills": [skill.to_dict() for skill in selected_skills]}

    async def reorder_skills(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reorder CD skills and update grouping information.

        Args:
            msg: IPC message containing:
                - skills_data: List of skill dictionaries with updated order

        Returns:
            Dictionary with "skills" key containing reordered skill list
                and "updated" key with count of updated skills

        Raises:
            RuntimeError: If skills_data missing or invalid
        """
        skills_data = msg.get("skills_data")
        if not skills_data or not isinstance(skills_data, list):
            raise RuntimeError("missing or invalid skills_data")

        updated_skills = self.daemon.skills_manager.reorder_skills(skills_data)
        return {"skills": [skill.to_dict() for skill in updated_skills], "updated": len(updated_skills)}
