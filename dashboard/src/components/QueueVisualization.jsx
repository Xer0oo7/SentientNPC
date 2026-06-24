import React, { useEffect, useState } from "react";
import { getAllQueueSnapshots } from "../api/client.js";

const PRIORITY_BAR = {
  CRITICAL: "bg-red-500",
  HIGH: "bg-orange-400",
  MEDIUM: "bg-yellow-400",
  LOW: "bg-gray-300",
  IDLE: "bg-stone-200",
};

const PRIORITY_TEXT = {
  CRITICAL: "text-red-800 bg-red-50",
  HIGH: "text-orange-800 bg-orange-50",
  MEDIUM: "text-yellow-900 bg-yellow-50",
  LOW: "text-gray-700 bg-gray-50",
  IDLE: "text-stone-500 bg-stone-50",
};

export default function QueueVisualization() {
  const [queues, setQueues] = useState({});

  useEffect(() => {
    async function load() {
      try {
        const data = await getAllQueueSnapshots();
        setQueues(data);
      } catch (err) {
        console.warn("Queue API error:", err);
      }
    }

    load();
    const timer = setInterval(load, 1000);
    return () => clearInterval(timer);
  }, []);

  const npcIds = Object.keys(queues);

  if (npcIds.length === 0) {
    return (
      <div className="rounded-lg border border-stone-200 bg-white p-6 text-center text-sm text-stone-400 shadow-sm">
        No NPC queues initialized. Start the simulation to see queues.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-stone-200 bg-white shadow-sm">
      <div className="border-b border-stone-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-stone-950">NPC Priority Queues</h2>
        <p className="mt-0.5 text-xs text-stone-400">Refreshing every 1s. Events sorted by priority (highest first).</p>
      </div>
      <div className="grid gap-px bg-stone-200 sm:grid-cols-2 lg:grid-cols-3">
        {npcIds.map((npcId) => {
          const events = queues[npcId] || [];
          return (
            <div key={npcId} className="bg-white p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-stone-900">{npcId}</h3>
                <span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-600">
                  {events.length} queued
                </span>
              </div>

              {events.length === 0 ? (
                <div className="mt-3 rounded-md bg-stone-50 p-3 text-center text-xs text-stone-400">
                  Queue empty
                </div>
              ) : (
                <div className="mt-3 space-y-1.5">
                  {events.map((event, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2 rounded-md bg-stone-50 p-2"
                    >
                      <div className={`mt-0.5 h-2 w-2 flex-shrink-0 rounded-full ${PRIORITY_BAR[event.priority_label] || PRIORITY_BAR.LOW}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${PRIORITY_TEXT[event.priority_label] || PRIORITY_TEXT.LOW}`}>
                            {event.priority_label}
                          </span>
                          <span className="text-xs font-medium text-stone-700">{event.event_type}</span>
                        </div>
                        <div className="mt-0.5 truncate text-[11px] text-stone-500">{event.description}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
