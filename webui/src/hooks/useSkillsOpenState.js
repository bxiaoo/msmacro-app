import { useCallback } from 'react'

const STORAGE_KEY = 'msmacro-skills-open-state'

/**
 * Custom hook to manage skill open/collapsed states in localStorage.
 *
 * This persists which skills have their expanded settings panel open
 * so the state survives tab switches and page refreshes.
 */
export function useSkillsOpenState() {
  /**
   * Get all stored open states
   * @returns {Object} Map of skillId -> boolean
   */
  const getAllOpenStates = useCallback(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      return stored ? JSON.parse(stored) : {}
    } catch (error) {
      console.error('Failed to load skill open states from localStorage:', error)
      return {}
    }
  }, [])

  /**
   * Get the open state for a specific skill
   * @param {string} skillId - The skill ID
   * @returns {boolean} True if skill is open, false otherwise
   */
  const getOpenState = useCallback((skillId) => {
    const states = getAllOpenStates()
    return states[skillId] || false
  }, [getAllOpenStates])

  /**
   * Set the open state for a specific skill
   * @param {string} skillId - The skill ID
   * @param {boolean} isOpen - Whether the skill should be open
   */
  const setOpenState = useCallback((skillId, isOpen) => {
    try {
      const states = getAllOpenStates()
      states[skillId] = isOpen
      localStorage.setItem(STORAGE_KEY, JSON.stringify(states))
    } catch (error) {
      console.error('Failed to save skill open state to localStorage:', error)
    }
  }, [getAllOpenStates])

  /**
   * Remove a skill's open state (useful when skill is deleted)
   * @param {string} skillId - The skill ID to remove
   */
  const removeOpenState = useCallback((skillId) => {
    try {
      const states = getAllOpenStates()
      delete states[skillId]
      localStorage.setItem(STORAGE_KEY, JSON.stringify(states))
    } catch (error) {
      console.error('Failed to remove skill open state from localStorage:', error)
    }
  }, [getAllOpenStates])

  /**
   * Clean up open states for skills that no longer exist
   * @param {Array<string>} validSkillIds - Array of current valid skill IDs
   */
  const cleanupOpenStates = useCallback((validSkillIds) => {
    try {
      const states = getAllOpenStates()
      const validIdSet = new Set(validSkillIds)
      let changed = false

      // Remove any stored IDs that are no longer valid
      for (const skillId in states) {
        if (!validIdSet.has(skillId)) {
          delete states[skillId]
          changed = true
        }
      }

      if (changed) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(states))
      }
    } catch (error) {
      console.error('Failed to cleanup skill open states from localStorage:', error)
    }
  }, [getAllOpenStates])

  return {
    getAllOpenStates,
    getOpenState,
    setOpenState,
    removeOpenState,
    cleanupOpenStates
  }
}
