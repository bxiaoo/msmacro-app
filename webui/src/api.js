// API helper with error handling
async function API(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
  
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { error: text || "non-json response" };
    }
  
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
      const err = new Error(msg);
      err.status = res.status;
      err.body = data;
      throw err;
    }
    return data;
  }

  function encodePath(p) {
    return (p || '').split('/').map(encodeURIComponent).join('/');
  }

  function toRel(p) {
    return (p || '').replace(/^\/+/, '');
  }
  
  // ---------- Status & Files ----------
  export function getStatus() {
    return API("/api/status");
  }
  
  export function listFiles() {
    return API("/api/files");
  }
  
  // ---------- Recording ----------
  export async function startRecord() {
    const r = await fetch("/api/record/start", { method: "POST" });
    if (!r.ok) throw new Error("Failed to start recording");
    return r.json().catch(() => ({ ok: true }));
  }
  
  // Stop recording with optional action: "save" | "discard" | ""
  export function stopRecord(action = "", name = "") {
    const body = { action };
    if (name) body.name = name;
    return API("/api/record/stop", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }
  
  // ---------- PostRecord Mode Actions ----------
  // Save the in-memory "last recording" (when in POSTRECORD mode)
  export function saveLast(name) {
    return API("/api/post/save", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  }
  
  // Preview play the last recording once
  export function previewLast(opts = {}) {
    return API("/api/post/preview", {
      method: "POST",
      body: JSON.stringify(opts),
    });
  }
  
  // Discard the last recording
  export function discardLast() {
    return API("/api/post/discard", {
      method: "POST",
      body: JSON.stringify({}),
    });
  }
  
  // ---------- Playback ----------
  // Play multiple files (playlist) or single file
  export function playSelection(names, opts = {}) {
    // Handle both array (playlist) and single string
    const list = Array.isArray(names) ? names : names ? [names] : [];
    if (!list.length) {
      throw new Error("playSelection expects a non-empty array or string");
    }

    const payload = {
      names: list,
      speed: opts.speed || 1.0,
      jitter_time: opts.jitter_time || 0.0,
      jitter_hold: opts.jitter_hold || 0.0,
      loop: opts.loop || 1,
      ignore_keys: opts.ignore_keys || [],
      ignore_tolerance: opts.ignore_tolerance || 0.0,
      active_skills: opts.active_skills || [],
    };

    return API("/api/play", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  
  // Backward compatibility alias
  export const play = playSelection;
  
  // Stop current playback or recording
  export function stop() {
    return API("/api/stop", { method: "POST" });
  }
  
  // ---------- CD Skills Management ----------
  export function listSkills() {
    return API("/api/skills");
  }

  export function saveSkill(skillData) {
    return API("/api/skills/save", {
      method: "POST",
      body: JSON.stringify(skillData),
    });
  }

  export function updateSkill(id, skillData) {
    return API(`/api/skills/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(skillData),
    });
  }

  export function deleteSkill(id) {
    return API(`/api/skills/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  export function getSelectedSkills() {
    return API("/api/skills/selected");
  }

  export function reorderSkills(skillsData) {
    return API("/api/skills/reorder", {
      method: "PUT",
      body: JSON.stringify(skillsData),
    });
  }

  // ---------- CV (Computer Vision) Management ----------
  export function getCVStatus() {
    return API("/api/cv/status");
  }

  export function getCVScreenshotURL() {
    // Return URL with timestamp to prevent caching
    return `/api/cv/screenshot?t=${Date.now()}`;
  }

  export function startCVCapture() {
    return API("/api/cv/start", {
      method: "POST",
    });
  }

  export function stopCVCapture() {
    return API("/api/cv/stop", {
      method: "POST",
    });
  }

  // ---------- CV Map Configuration ----------
  export function listMapConfigs() {
    return API("/api/cv/map-configs");
  }

  export function createMapConfig(name, tl_x, tl_y, width, height) {
    return API("/api/cv/map-configs", {
      method: "POST",
      body: JSON.stringify({
        name,
        tl_x,
        tl_y,
        width,
        height,
      }),
    });
  }

  export function deleteMapConfig(name) {
    return API(`/api/cv/map-configs/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
  }

  export function activateMapConfig(name) {
    return API(`/api/cv/map-configs/${encodeURIComponent(name)}/activate`, {
      method: "POST",
    });
  }

  export function getActiveMapConfig() {
    return API("/api/cv/map-configs/active");
  }

  export function deactivateMapConfig() {
    return API("/api/cv/map-configs/deactivate", {
      method: "POST",
    });
  }

  export function getMiniMapPreviewURL(x, y, w, h) {
    // Return URL with cache busting timestamp
    return `/api/cv/mini-map-preview?x=${x}&y=${y}&w=${w}&h=${h}&t=${Date.now()}`;
  }

  // ---------- Departure Points ----------
  export function addDeparturePoint(mapName, x, y, name = null, toleranceMode = "both", toleranceValue = 5) {
    return API(`/api/cv/map-configs/${encodeURIComponent(mapName)}/departure-points`, {
      method: "POST",
      body: JSON.stringify({
        x,
        y,
        name,
        tolerance_mode: toleranceMode,
        tolerance_value: toleranceValue,
      }),
    });
  }

  export function removeDeparturePoint(mapName, pointId) {
    return API(`/api/cv/map-configs/${encodeURIComponent(mapName)}/departure-points/${encodeURIComponent(pointId)}`, {
      method: "DELETE",
    });
  }

  export function updateDeparturePoint(mapName, pointId, updates) {
    return API(`/api/cv/map-configs/${encodeURIComponent(mapName)}/departure-points/${encodeURIComponent(pointId)}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    });
  }

  export function reorderDeparturePoints(mapName, orderedIds) {
    return API(`/api/cv/map-configs/${encodeURIComponent(mapName)}/departure-points/reorder`, {
      method: "POST",
      body: JSON.stringify({
        ordered_ids: orderedIds,
      }),
    });
  }

  export function getDeparturePointsStatus() {
    return API("/api/cv/departure-points/status");
  }

  // ---------- File Management ----------
  export async function renameFile(oldName, newName) {
    return API("/api/files/rename", {
      method: "POST",
      body: JSON.stringify({ old: toRel(oldName), new: toRel(newName) }),
    });
  }
  
  export async function deleteFile(name) {
    const rel = toRel(name);
    return API(`/api/files/${encodePath(rel)}`, {
      method: "DELETE",
    });
  }
  
  // Delete folder (with optional recursion)
  export function deleteFolder(path, recurse = false) {
    const rel = toRel(path);                    // strip accidental leading slash
    const q   = recurse ? '?recurse=1' : '';
    return API(`/api/folders/${encodePath(rel)}${q}`, { method: 'DELETE' });
  }
  
  // ---------- Real-time Events (SSE) ----------
  export class EventStream {
    constructor(onMode, onFiles) {
      this.onMode = onMode;
      this.onFiles = onFiles;
      this.source = null;
      this.reconnectTimer = null;
      this.connect();
    }
  
    connect() {
      if (this.source) {
        this.source.close();
      }
  
      this.source = new EventSource("/api/events");
  
      this.source.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "mode" && this.onMode) {
            this.onMode(data.mode);
          } else if (data.type === "files" && this.onFiles) {
            this.onFiles(data.files);
          }
        } catch (err) {
          console.error("EventStream parse error:", err);
        }
      };
  
      this.source.onerror = () => {
        console.log("EventStream connection lost, reconnecting...");
        this.source.close();
        
        // Reconnect after 2 seconds
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
        this.reconnectTimer = setTimeout(() => this.connect(), 2000);
      };
  
      this.source.onopen = () => {
        console.log("EventStream connected");
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };
    }
  
    close() {
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      if (this.source) {
        this.source.close();
        this.source = null;
      }
    }
  }

  // ---------- System Stats ----------
  export function getSystemStats() {
    return API("/api/system/stats");
  }

  // ---------- Object Detection ----------
  export function getObjectDetectionStatus() {
    return API("/api/cv/object-detection/status");
  }

  export function startObjectDetection(config = null) {
    return API("/api/cv/object-detection/start", {
      method: "POST",
      body: JSON.stringify({ config })
    });
  }

  export function stopObjectDetection() {
    return API("/api/cv/object-detection/stop", {
      method: "POST"
    });
  }

  export function updateObjectDetectionConfig(config) {
    return API("/api/cv/object-detection/config", {
      method: "POST",
      body: JSON.stringify({ config })
    });
  }

  export function saveCalibrationSample(filename = null, metadata = {}) {
    return API("/api/cv/save-calibration-sample", {
      method: "POST",
      body: JSON.stringify({ filename, metadata })
    });
  }

  export function listCalibrationSamples() {
    return API("/api/cv/calibration-samples");
  }

  export function getCalibrationSampleURL(filename) {
    return `/api/cv/calibration-sample/${encodeURIComponent(filename)}`;
  }

  export function downloadAllCalibrationSamples() {
    // Trigger browser download by opening URL
    window.location.href = "/api/cv/calibration-samples/download-zip";
  }

  export function deleteCalibrationSample(filename) {
    return API(`/api/cv/calibration-sample/${encodeURIComponent(filename)}`, {
      method: "DELETE"
    });
  }
