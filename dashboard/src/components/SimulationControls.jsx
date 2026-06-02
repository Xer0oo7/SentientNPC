import React, { useCallback, useEffect, useState } from "react";
import {
  getSimulationStatus,
  injectEvent,
  startSimulation,
  stopSimulation,
} from "../api/client.js";

const EVENT_TYPES = [
  { value: "player_stole", label: "Player Stole", priority: 1 },
  { value: "player_attacked_ally", label: "Player Attacked Ally", priority: 0 },
  { value: "npc_under_attack", label: "NPC Under Attack", priority: 0 },
  { value: "threat_detected", label: "Threat Detected", priority: 1 },
  { value: "sound_loud", label: "Loud Sound", priority: 1 },
  { value: "player_helped_npc", label: "Player Helped NPC", priority: 2 },
  { value: "player_completed_quest", label: "Quest Completed", priority: 2 },
  { value: "give_gift", label: "Gift Given", priority: 2 },
  { value: "player_said_hello", label: "Player Said Hello", priority: 3 },
  { value: "ambient_observation", label: "Ambient Observation", priority: 4 },
];

export default function SimulationControls() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  // Inject form state
  const [injectNpcId, setInjectNpcId] = useState("");
  const [injectEventType, setInjectEventType] = useState(EVENT_TYPES[0].value);
  const [injectDesc, setInjectDesc] = useState("");
  const [injectResult, setInjectResult] = useState(null);

  const refreshStatus = useCallback(async () => {
    try {
      const data = await getSimulationStatus();
      setStatus(data);
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const timer = setInterval(refreshStatus, 1000);
    return () => clearInterval(timer);
  }, [refreshStatus]);

  const handleStart = async () => {
    setLoading(true);
    try {
      await startSimulation();
      await refreshStatus();
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopSimulation();
      await refreshStatus();
    } finally {
      setLoading(false);
    }
  };

  const handleInject = async (e) => {
    e.preventDefault();
    if (!injectNpcId || !injectDesc) return;
    try {
      const result = await injectEvent(injectNpcId, injectEventType, injectDesc);
      setInjectResult(result);
      setInjectDesc("");
      await refreshStatus();
      // Auto-clear result
      setTimeout(() => setInjectResult(null), 3000);
    } catch (err) {
      setInjectResult({ error: err.message });
    }
  };

  const npcIds = status ? Object.keys(status.queue_depths || {}) : [];

  // Set default NPC ID when list loads
  useEffect(() => {
    if (npcIds.length > 0 && !injectNpcId) {
      setInjectNpcId(npcIds[0]);
    }
  }, [npcIds, injectNpcId]);

  return (
    <div className="space-y-4">
      {/* Status + Controls */}
      <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-stone-950">Simulation Engine</h2>
            {status ? (
              <div className="mt-2 flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1.5">
                  <div className={`h-2.5 w-2.5 rounded-full ${status.running ? "bg-green-500 animate-pulse" : "bg-stone-300"}`} />
                  <span className="text-stone-600">{status.running ? "Running" : "Stopped"}</span>
                </div>
                <div className="text-stone-500">
                  Tick: <span className="font-mono font-semibold text-stone-900">{status.tick}</span>
                </div>
                <div className="text-stone-500">
                  Interval: <span className="font-medium text-stone-700">{status.tick_interval_ms}ms</span>
                </div>
                <div className="text-stone-500">
                  WS: <span className="font-medium text-stone-700">{status.ws_subscribers}</span>
                </div>
              </div>
            ) : (
              <p className="mt-1 text-sm text-stone-400">Connecting to backend...</p>
            )}
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleStart}
              disabled={loading || status?.running}
              className="rounded-md bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              ▶ Start
            </button>
            <button
              onClick={handleStop}
              disabled={loading || !status?.running}
              className="rounded-md bg-stone-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-stone-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              ⏹ Stop
            </button>
          </div>
        </div>

        {/* Queue depths */}
        {status && Object.keys(status.queue_depths || {}).length > 0 && (
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {Object.entries(status.queue_depths).map(([npcId, depth]) => (
              <div key={npcId} className="rounded-md bg-stone-50 p-2 text-center">
                <div className="text-[10px] uppercase tracking-wide text-stone-400">{npcId}</div>
                <div className="mt-0.5 text-lg font-bold text-stone-900">{depth}</div>
                <div className="text-[10px] text-stone-400">queued</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Event Injection */}
      <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-stone-950">Inject Event</h2>
        <form onSubmit={handleInject} className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-stone-500">NPC</label>
            <select
              value={injectNpcId}
              onChange={(e) => setInjectNpcId(e.target.value)}
              className="rounded-md border border-stone-300 px-3 py-1.5 text-sm text-stone-900"
            >
              {npcIds.map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-stone-500">Event Type</label>
            <select
              value={injectEventType}
              onChange={(e) => setInjectEventType(e.target.value)}
              className="rounded-md border border-stone-300 px-3 py-1.5 text-sm text-stone-900"
            >
              {EVENT_TYPES.map((et) => (
                <option key={et.value} value={et.value}>{et.label}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-xs text-stone-500">Description</label>
            <input
              type="text"
              value={injectDesc}
              onChange={(e) => setInjectDesc(e.target.value)}
              placeholder="What happened?"
              className="w-full rounded-md border border-stone-300 px-3 py-1.5 text-sm text-stone-900 placeholder-stone-400"
            />
          </div>
          <button
            type="submit"
            disabled={!injectNpcId || !injectDesc}
            className="rounded-md bg-violet-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Inject
          </button>
        </form>
        {injectResult && (
          <div className={`mt-2 rounded-md px-3 py-2 text-xs ${injectResult.error ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
            {injectResult.error ? `Error: ${injectResult.error}` : `✓ Enqueued "${injectResult.event_type}" for ${injectResult.npc_id} (queue depth: ${injectResult.queue_depth})`}
          </div>
        )}
      </div>
    </div>
  );
}
