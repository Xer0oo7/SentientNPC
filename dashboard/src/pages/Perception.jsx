import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  getWorldSnapshot,
  moveEntity,
  getNPCFOV,
  getNearbyEntities,
  getRecentPerceptionEvents,
  triggerSound,
} from "../api/client.js";
import WorldMap from "../components/WorldMap.jsx";
import PerceptionPanel from "../components/PerceptionPanel.jsx";

export default function Perception() {
  const [worldData, setWorldData] = useState(null);
  const [selectedNpcId, setSelectedNpcId] = useState(null);
  const [fovData, setFovData] = useState(null);
  const [nearbyEntities, setNearbyEntities] = useState([]);
  const [perceptionEvents, setPerceptionEvents] = useState([]);
  const [soundRipples, setSoundRipples] = useState([]);
  const [feedback, setFeedback] = useState(null);
  const [soundType, setSoundType] = useState("combat");
  const animRef = useRef(null);

  // Fetch world snapshot on interval
  useEffect(() => {
    let active = true;
    const fetchWorld = async () => {
      try {
        const data = await getWorldSnapshot();
        if (active) setWorldData(data);
      } catch { /* backend not running */ }
    };
    fetchWorld();
    const timer = setInterval(fetchWorld, 800);
    return () => { active = false; clearInterval(timer); };
  }, []);

  // Fetch perception events
  useEffect(() => {
    let active = true;
    const fetchEvents = async () => {
      try {
        const events = await getRecentPerceptionEvents(30);
        if (active) setPerceptionEvents(events);
      } catch { /* ignore */ }
    };
    fetchEvents();
    const timer = setInterval(fetchEvents, 1000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  // Fetch FOV and nearby when selected NPC changes
  useEffect(() => {
    if (!selectedNpcId) {
      setFovData(null);
      setNearbyEntities([]);
      return;
    }

    let active = true;
    const fetchNpcPerception = async () => {
      try {
        const [fov, nearby] = await Promise.all([
          getNPCFOV(selectedNpcId),
          getNearbyEntities(selectedNpcId),
        ]);
        if (active) {
          setFovData(fov);
          setNearbyEntities(nearby?.nearby || []);
        }
      } catch { /* ignore */ }
    };
    fetchNpcPerception();
    const timer = setInterval(fetchNpcPerception, 1000);
    return () => { active = false; clearInterval(timer); };
  }, [selectedNpcId]);

  // Sound ripple animation
  useEffect(() => {
    if (soundRipples.length === 0) return;

    const animate = () => {
      setSoundRipples((prev) =>
        prev
          .map((r) => ({ ...r, progress: r.progress + 0.02 }))
          .filter((r) => r.progress < 1)
      );
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [soundRipples.length > 0]);

  const handleEntityClick = useCallback((entity) => {
    if (entity.entity_type === "npc") {
      setSelectedNpcId((prev) => (prev === entity.id ? null : entity.id));
    }
  }, []);

  const handleMapClick = useCallback(async (wx, wz) => {
    try {
      await moveEntity("player_001", wx, wz);
      // Refresh world
      const data = await getWorldSnapshot();
      setWorldData(data);
      setFeedback({ type: "success", msg: `Player moved to (${wx.toFixed(1)}, ${wz.toFixed(1)})` });
      setTimeout(() => setFeedback(null), 2000);
    } catch (err) {
      setFeedback({ type: "error", msg: "Failed to move player" });
      setTimeout(() => setFeedback(null), 2000);
    }
  }, []);

  const handleTriggerSound = useCallback(async () => {
    // Trigger sound at player position
    const player = worldData?.entities?.find((e) => e.id === "player_001");
    if (!player) return;

    try {
      const result = await triggerSound(player.x, player.z, soundType, 1.0);
      setSoundRipples((prev) => [
        ...prev,
        { x: player.x, z: player.z, radius: 30, progress: 0 },
      ]);
      setFeedback({
        type: "success",
        msg: `Sound triggered — ${result.npcs_affected} NPCs heard it`,
      });
      setTimeout(() => setFeedback(null), 3000);
    } catch {
      setFeedback({ type: "error", msg: "Failed to trigger sound" });
      setTimeout(() => setFeedback(null), 2000);
    }
  }, [worldData, soundType]);

  // Filter events for selected NPC
  const filteredEvents = selectedNpcId
    ? perceptionEvents.filter((e) => e.npc_id === selectedNpcId)
    : perceptionEvents;

  const selectedConfig = fovData
    ? {
        vision_range: fovData.vision_range,
        vision_fov: fovData.vision_fov,
        hearing_range: fovData.hearing_range,
      }
    : null;

  return (
    <div>
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-stone-900">Perception System</h1>
        <p className="text-sm text-stone-500 mt-1">
          2D world map — click an NPC to inspect its senses, click the map to move the player
        </p>
      </div>

      {/* Feedback toast */}
      {feedback && (
        <div
          className={`mb-4 rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
            feedback.type === "success"
              ? "bg-teal-50 text-teal-700 border border-teal-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          {feedback.msg}
        </div>
      )}

      {/* Sound trigger control */}
      <div className="mb-4 flex items-center gap-3 rounded-lg border border-stone-200 bg-white px-4 py-3">
        <span className="text-sm font-medium text-stone-700">Trigger Sound at Player:</span>
        <select
          value={soundType}
          onChange={(e) => setSoundType(e.target.value)}
          className="rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-sm text-stone-700"
        >
          <option value="combat">Combat</option>
          <option value="explosion">Explosion</option>
          <option value="speech">Speech</option>
          <option value="stealth">Stealth</option>
          <option value="alert">Alert</option>
          <option value="ambient">Ambient</option>
        </select>
        <button
          onClick={handleTriggerSound}
          className="rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-600 transition"
        >
          🔊 Trigger Sound
        </button>
      </div>

      {/* Main layout: Map + Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <div className="rounded-lg border border-stone-200 bg-stone-900 p-2">
            {worldData ? (
              <WorldMap
                entities={worldData.entities || []}
                zones={worldData.zones || {}}
                selectedNpcId={selectedNpcId}
                fovData={fovData}
                onEntityClick={handleEntityClick}
                onMapClick={handleMapClick}
                soundRipples={soundRipples}
              />
            ) : (
              <div className="flex h-96 items-center justify-center text-stone-500 text-sm">
                Waiting for backend — start the server and simulation
              </div>
            )}
          </div>
          {/* Entity count summary */}
          {worldData && (
            <div className="mt-2 flex items-center gap-4 text-xs text-stone-400">
              <span>{worldData.entity_count} entities</span>
              <span>•</span>
              <span>{Object.keys(worldData.zones || {}).length} zones</span>
              <span>•</span>
              <span>{perceptionEvents.length} recent perception events</span>
            </div>
          )}
        </div>

        {/* Right panel */}
        <div>
          <PerceptionPanel
            selectedNpcId={selectedNpcId}
            config={selectedConfig}
            nearbyEntities={nearbyEntities}
            recentEvents={filteredEvents}
          />
        </div>
      </div>
    </div>
  );
}
