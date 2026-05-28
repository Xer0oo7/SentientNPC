import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

export async function getAllNPCs() {
  const response = await api.get("/npc/");
  return response.data;
}

export async function getNPC(id) {
  const response = await api.get(`/npc/${id}`);
  return response.data;
}

export async function getMemories(npc_id) {
  const response = await api.get(`/memory/${npc_id}`);
  return response.data;
}

export async function getRelationships(npc_id) {
  const response = await api.get(`/relationship/${npc_id}`);
  return response.data;
}

export async function getAnalyticsOverview() {
  const response = await api.get("/analytics/overview");
  return response.data;
}

export async function getNPCAnalytics(id) {
  const response = await api.get(`/analytics/npc/${id}`);
  return response.data;
}

export default api;
