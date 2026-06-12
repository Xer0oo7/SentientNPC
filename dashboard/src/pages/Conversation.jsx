import React, { useEffect, useRef, useState } from "react";
import {
  Chart as ChartJS,
  Filler,
  LineElement,
  PointElement,
  RadialLinearScale,
  Tooltip,
} from "chart.js";
import { Radar } from "react-chartjs-2";

import {
  getAllNPCs,
  getDialogueHistory,
  sendDialogue,
} from "../api/client.js";
import EmotionBadge from "../components/EmotionBadge.jsx";

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip);

const EMOTION_COLORS = {
  happy: "#22c55e",
  angry: "#ef4444",
  fearful: "#eab308",
  sad: "#3b82f6",
  neutral: "#78716c",
  excited: "#a855f7",
};

export default function Conversation() {
  const [npcs, setNpcs] = useState([]);
  const [selectedNpc, setSelectedNpc] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef(null);

  // Load NPC list on mount
  useEffect(() => {
    async function load() {
      try {
        const data = await getAllNPCs();
        setNpcs(data);
      } catch {
        setError("Failed to load NPCs.");
      }
    }
    load();
  }, []);

  // Load dialogue history when NPC changes
  useEffect(() => {
    if (!selectedNpc) return;
    async function loadHistory() {
      try {
        const history = await getDialogueHistory(selectedNpc.id);
        // API returns newest first, reverse for chronological display
        const formatted = history.reverse().flatMap((entry) => [
          {
            role: "player",
            text: entry.player_message,
            timestamp: entry.timestamp,
          },
          {
            role: "npc",
            text: entry.npc_response,
            timestamp: entry.timestamp,
            emotion: selectedNpc.emotion,
          },
        ]);
        setMessages(formatted);
      } catch {
        setMessages([]);
      }
    }
    loadHistory();
  }, [selectedNpc]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleNpcSelect(e) {
    const npc = npcs.find((n) => n.id === e.target.value);
    setSelectedNpc(npc || null);
    setMessages([]);
    setError("");
  }

  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim() || !selectedNpc || sending) return;

    const playerMsg = input.trim();
    setInput("");
    setSending(true);
    setError("");

    // Optimistically add player message
    setMessages((prev) => [
      ...prev,
      { role: "player", text: playerMsg, timestamp: new Date().toISOString() },
    ]);

    try {
      const response = await sendDialogue(selectedNpc.id, playerMsg);
      setMessages((prev) => [
        ...prev,
        {
          role: "npc",
          text: response.response,
          timestamp: new Date().toISOString(),
          emotion: response.emotion,
          relationship_score: response.relationship_score,
        },
      ]);
      // Update selected NPC's emotion from response
      setSelectedNpc((prev) => ({
        ...prev,
        emotion: response.emotion,
      }));
    } catch {
      setError("Failed to get response. Is the backend running?");
    } finally {
      setSending(false);
    }
  }

  // Radar chart data for sidebar
  const radarData = selectedNpc
    ? {
        labels: ["aggressive", "friendly", "greedy", "bravery", "curiosity", "loyalty"],
        datasets: [
          {
            data: ["aggressive", "friendly", "greedy", "bravery", "curiosity", "loyalty"].map(
              (k) => selectedNpc.personality?.[k] || 0
            ),
            backgroundColor: "rgba(20, 184, 166, 0.15)",
            borderColor: "rgb(13, 148, 136)",
            borderWidth: 2,
            pointBackgroundColor: "rgb(13, 148, 136)",
            pointRadius: 3,
          },
        ],
      }
    : null;

  const radarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: { min: 0, max: 100, ticks: { display: false }, pointLabels: { font: { size: 10 } } },
    },
    plugins: { legend: { display: false }, tooltip: { enabled: false } },
  };

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-stone-950">Conversation</h1>
        <p className="mt-1 text-sm text-stone-500">
          Talk to any NPC. Their responses are shaped by personality, memories, emotions, and your relationship.
        </p>
      </div>

      {/* NPC Selector */}
      <div className="flex items-center gap-3">
        <label htmlFor="npc-select" className="text-sm font-medium text-stone-700">
          Talk to:
        </label>
        <select
          id="npc-select"
          className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          value={selectedNpc?.id || ""}
          onChange={handleNpcSelect}
        >
          <option value="">Select an NPC...</option>
          {npcs.map((npc) => (
            <option key={npc.id} value={npc.id}>
              {npc.name} ({npc.id})
            </option>
          ))}
        </select>
      </div>

      {selectedNpc && (
        <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
          {/* Chat Window */}
          <div className="flex flex-col rounded-lg border border-stone-200 bg-white shadow-sm" style={{ height: "560px" }}>
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {messages.length === 0 && (
                <div className="flex h-full items-center justify-center">
                  <p className="text-sm text-stone-400">
                    Start a conversation with {selectedNpc.name}...
                  </p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === "player" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                      msg.role === "player"
                        ? "bg-teal-600 text-white rounded-br-md"
                        : "bg-stone-100 text-stone-900 rounded-bl-md"
                    }`}
                  >
                    {msg.role === "npc" && (
                      <div className="mb-1 flex items-center gap-2">
                        <span className="text-xs font-semibold text-stone-700">
                          {selectedNpc.name}
                        </span>
                        {msg.emotion && (
                          <span
                            className="inline-block h-2 w-2 rounded-full"
                            style={{ backgroundColor: EMOTION_COLORS[msg.emotion] || "#78716c" }}
                            title={msg.emotion}
                          />
                        )}
                      </div>
                    )}
                    {msg.text}
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {sending && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-md bg-stone-100 px-4 py-3">
                    <div className="flex items-center gap-1">
                      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-stone-400" style={{ animationDelay: "0ms" }} />
                      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-stone-400" style={{ animationDelay: "150ms" }} />
                      <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-stone-400" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <form
              onSubmit={handleSend}
              className="flex items-center gap-2 border-t border-stone-200 px-4 py-3"
            >
              <input
                type="text"
                className="flex-1 rounded-lg border border-stone-300 bg-stone-50 px-4 py-2.5 text-sm text-stone-900 placeholder-stone-400 focus:border-teal-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-teal-500"
                placeholder={`Say something to ${selectedNpc.name}...`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={sending}
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                className="rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Send
              </button>
            </form>

            {error && (
              <div className="border-t border-red-100 bg-red-50 px-4 py-2 text-xs text-red-700">
                {error}
              </div>
            )}
          </div>

          {/* NPC Info Sidebar */}
          <div className="space-y-3">
            {/* Name & Emotion */}
            <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
              <h3 className="text-base font-semibold text-stone-950">{selectedNpc.name}</h3>
              <p className="mt-0.5 text-xs text-stone-500">{selectedNpc.id}</p>
              <div className="mt-3 flex items-center gap-2">
                <EmotionBadge emotion={selectedNpc.emotion} />
                <span className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-teal-700">
                  {selectedNpc.fsm_state}
                </span>
              </div>
            </div>

            {/* Personality Radar */}
            {radarData && (
              <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                  Personality
                </h4>
                <div className="mt-2 h-44">
                  <Radar data={radarData} options={radarOptions} />
                </div>
              </div>
            )}

            {/* Stats */}
            <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                Relationship
              </h4>
              <div className="mt-2 text-2xl font-bold text-stone-950">
                {selectedNpc.reputation >= 0 ? "+" : ""}
                {selectedNpc.reputation}
              </div>
              <div className="mt-1 text-xs text-stone-500">Reputation score</div>
            </div>

            {/* Zone */}
            <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                Location
              </h4>
              <div className="mt-2 text-sm font-medium text-stone-900">
                {selectedNpc.zone || "Unknown"}
              </div>
              <div className="mt-1 text-xs text-stone-500">
                Position: ({selectedNpc.pos_x}, {selectedNpc.pos_z})
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
