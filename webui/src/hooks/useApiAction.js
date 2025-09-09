import { useState } from 'react';

/**
 * Hook for managing API action states following the "Always Work™" principle.
 * Prevents multiple API calls and provides loading states for buttons.
 */
export function useApiAction() {
  const [pendingActions, setPendingActions] = useState(new Set());

  const executeAction = async (actionKey, apiCall, onSuccess) => {
    // Prevent duplicate calls while one is in progress
    if (pendingActions.has(actionKey)) {
      console.warn(`Action "${actionKey}" already in progress, ignoring duplicate call`);
      return;
    }

    // Mark action as pending
    setPendingActions(prev => new Set([...prev, actionKey]));

    try {
      const result = await apiCall();
      onSuccess?.(result);
      return result;
    } catch (error) {
      console.error(`Action "${actionKey}" failed:`, error);
      throw error;
    } finally {
      // Always remove from pending, even if error occurred
      setPendingActions(prev => {
        const next = new Set(prev);
        next.delete(actionKey);
        return next;
      });
    }
  };

  const isPending = (actionKey) => pendingActions.has(actionKey);

  return { executeAction, isPending };
}