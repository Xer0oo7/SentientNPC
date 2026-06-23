import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

// ── NPC ──

export async function getAllNPCs() {
  const response = await api.get("/npc/");
  return response.data;
}

export async function getNPC(id) {
  const response = await api.get(`/npc/${id}`);
  return response.data;
}

// ── Memory ──

export async function getMemories(npc_id) {
  const response = await api.get(`/memory/${npc_id}`);
  return response.data;
}

// ── Relationship ──

export async function getRelationships(npc_id) {
  const response = await api.get(`/relationship/${npc_id}`);
  return response.data;
}

// ── Analytics ──

export async function getAnalyticsOverview() {
  const response = await api.get("/analytics/overview");
  return response.data;
}

export async function getNPCAnalytics(id) {
  const response = await api.get(`/analytics/npc/${id}`);
  return response.data;
}

// ── Simulation ──

export async function startSimulation() {
  const response = await api.post("/simulation/start");
  return response.data;
}

export async function stopSimulation() {
  const response = await api.post("/simulation/stop");
  return response.data;
}

export async function getSimulationStatus() {
  const response = await api.get("/simulation/status");
  return response.data;
}

export async function injectEvent(npcId, eventType, description, priority = null, location = null) {
  const response = await api.post("/simulation/inject", {
    npc_id: npcId,
    event_type: eventType,
    description,
    priority,
    location,
  });
  return response.data;
}

export async function getRecentEvents(limit = 50) {
  const response = await api.get(`/simulation/events?limit=${limit}`);
  return response.data;
}

export async function getAllQueueSnapshots() {
  const response = await api.get("/simulation/queues");
  return response.data;
}

export async function getNPCQueueSnapshot(npcId) {
  const response = await api.get(`/simulation/queues/${npcId}`);
  return response.data;
}

export async function getNPCSTMSnapshot(npcId) {
  const response = await api.get(`/simulation/memory/${npcId}`);
  return response.data;
}

/**
 * Create a WebSocket connection to the simulation event stream.
 * Returns the WebSocket instance. Caller is responsible for .onmessage, .onclose, etc.
 */
export function createSimulationWebSocket() {
  return new WebSocket("ws://localhost:8000/simulation/ws");
}

// ── Perception ──

export async function getWorldSnapshot() {
  const response = await api.get("/perception/world");
  return response.data;
}

export async function moveEntity(entityId, x, z, facingAngle = null, zone = null) {
  const response = await api.patch(`/perception/move/${entityId}`, {
    x,
    z,
    facing_angle: facingAngle,
    zone,
  });
  return response.data;
}

export async function getNPCFOV(npcId) {
  const response = await api.get(`/perception/fov/${npcId}`);
  return response.data;
}

export async function getNearbyEntities(npcId) {
  const response = await api.get(`/perception/nearby/${npcId}`);
  return response.data;
}

export async function triggerSound(x, z, soundType, loudness = 1.0) {
  const response = await api.post("/perception/sound", {
    x,
    z,
    sound_type: soundType,
    loudness,
  });
  return response.data;
}

export async function getPerceptionConfig(npcId) {
  const response = await api.get(`/perception/config/${npcId}`);
  return response.data;
}

export async function updatePerceptionConfig(npcId, config) {
  const response = await api.patch(`/perception/config/${npcId}`, config);
  return response.data;
}

export async function getRecentPerceptionEvents(limit = 50) {
  const response = await api.get(`/perception/events?limit=${limit}`);
  return response.data;
}

// ── Dialogue ──

export async function sendDialogue(npcId, playerMessage, playerId = "player_001") {
  const response = await api.post(`/dialogue/${npcId}`, {
    player_message: playerMessage,
    player_id: playerId,
  });
  return response.data;
}

export async function getDialogueHistory(npcId) {
  const response = await api.get(`/dialogue/${npcId}/history`);
  return response.data;
}

export default api;
