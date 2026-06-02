import React, { useEffect, useRef, useState } from "react";
import { createSimulationWebSocket, getRecentEvents } from "../api/client.js";

const PRIORITY_COLORS = {
  CRITICAL: "bg-red-100 text-red-800 ring-red-300",
  HIGH: "bg-orange-100 text-orange-800 ring-orange-300",
  MEDIUM: "bg-yellow-100 text-yellow-900 ring-yellow-300",
  LOW: "bg-gray-100 text-gray-700 ring-gray-300",
  IDLE: "bg-stone-100 text-stone-500 ring-stone-200",
};

const PRIORITY_DOT = {
  CRITICAL: "bg-red-500",
  HIGH: "bg-orange-500",
  MEDIUM: "bg-yellow-500",
  LOW: "bg-gray-400",
  IDLE: "bg-stone-300",
};

export default function EventFeed({ maxEvents = 100 }) {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef(null);
  const wsRef = useRef(null);

  // Load recent events via REST on mount
  useEffect(() => {
    async function loadHistory() {
      try {
        const history = await getRecentEvents(maxEvents);
        setEvents(history);
      } catch {
        // Backend may not be running
      }
    }
    loadHistory();
  }, [maxEvents]);

  // WebSocket connection
  useEffect(() => {
    function connect() {
      const ws = createSimulationWebSocket();
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data);
          setEvents((prev) => {
            const updated = [event, ...prev];
            return updated.slice(0, maxEvents);
          });
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 2 seconds
        setTimeout(connect, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [maxEvents]);

  // Auto-scroll to top when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events.length]);

  return (
    <div className="rounded-lg border border-stone-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-stone-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-stone-950">Live Event Feed</h2>
        <div className="flex items-center gap-2">
          <div className={`h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
          <span className="text-xs text-stone-500">{connected ? "Connected" : "Disconnected"}</span>
        </div>
      </div>
      <div ref={scrollRef} className="max-h-[480px] overflow-y-auto">
        {events.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-stone-400">
            No events yet. Start the simulation and inject events to see them here.
          </div>
        ) : (
          <div className="divide-y divide-stone-100">
            {events.map((event, idx) => (
              <div
                key={`${event.tick}-${event.npc_id}-${idx}`}
                className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-stone-50"
                style={{
                  animation: idx === 0 ? "slideIn 0.3s ease-out" : "none",
                }}
              >
                <div className={`mt-1.5 h-2.5 w-2.5 flex-shrink-0 rounded-full ${PRIORITY_DOT[event.priority_label] || PRIORITY_DOT.LOW}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-stone-900">{event.npc_id}</span>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ${PRIORITY_COLORS[event.priority_label] || PRIORITY_COLORS.LOW}`}>
                      {event.priority_label}
                    </span>
                    <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] font-mono text-stone-500">
                      tick {event.tick}
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-stone-700">{event.description}</div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-stone-500">
                    <span>Event: <span className="font-medium text-stone-600">{event.event_type}</span></span>
                    {event.action_taken && (
                      <span>Action: <span className="font-medium text-teal-700">{event.action_taken}</span></span>
                    )}
                    {event.emotion_shift && (
                      <span>Emotion: <span className="text-stone-600">{event.emotion_shift.from}</span> → <span className="font-medium text-purple-700">{event.emotion_shift.to}</span></span>
                    )}
                    {event.memory_created && (
                      <span className="text-emerald-600">💾 Memory</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(20px); }
          to   { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
