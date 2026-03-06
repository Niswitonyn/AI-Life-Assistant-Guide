/**
 * Machine-local authentication utilities
 *
 * Generates and manages a unique, per-machine identifier for local authentication.
 * This eliminates the security risk of hardcoded credentials in the codebase.
 *
 * On first launch:
 *   1. Generates a unique machine identifier (v4 UUID)
 *   2. Stores it securely in electron-store via IPC handlers
 *   3. Creates a deterministic email/password from this ID
 *
 * On subsequent launches:
 *   1. Retrieves the stored machine ID from secure storage
 *   2. Uses the same derived credentials
 */

// Use window.electronAPI (exposed via preload script) for IPC
// This works with contextIsolation: true and nodeIntegration: false

/**
 * Generate a UUID v4 using crypto.randomUUID (built-in, no external deps)
 */
function generateUUID() {
  return crypto.randomUUID();
}

/**
 * Get or create a unique machine-local credential pair
 * Uses Electron's IPC to communicate with secure storage via electron-store
 */
export async function getMachineCredentials() {
  try {
    // Try to retrieve existing machine ID from secure storage
    let stored = null;
    if (window.electronAPI) {
      stored = await window.electronAPI.secureGet("machine_id");
    }

    if (stored?.status === "ok" && stored.value) {
      return {
        email: `jarvis@machine.${stored.value.substring(0, 8)}`,
        password: stored.value,
        machineId: stored.value,
      };
    }

    // Generate new machine ID on first launch
    const machineId = generateUUID();

    // Store it securely - this goes through electron.js which encrypts it
    if (window.electronAPI) {
      try {
        await window.electronAPI.secureSet("machine_id", machineId);
      } catch (storeError) {
        console.warn("Could not persist machine ID to secure storage:", storeError);
        // Continue anyway with the in-memory ID for this session
      }
    }

    return {
      email: `jarvis@machine.${machineId.substring(0, 8)}`,
      password: machineId,
      machineId,
    };
  } catch (error) {
    console.error("Failed to get machine credentials:", error);

    throw new Error(
      "Could not initialize machine-local authentication. Ensure the app is running with proper permissions."
    );
  }
}

