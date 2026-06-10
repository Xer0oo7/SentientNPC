import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getAnalyticsOverview } from "../api/client.js";
import EmotionBadge from "../components/EmotionBadge.jsx";
import ReputationBar from "../components/ReputationBar.jsx";

export default function Overview() {
  const [npcs, setNpcs] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const data = await getAnalyticsOverview();
        if (mounted) {
          setNpcs(data);
          setError("");
        }
      } catch (err) {
        if (mounted) setError("Unable to reach backend analytics.");
      }
    }

    load();
    const timer = setInterval(load, 5000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <section className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-stone-950">NPC Overview</h1>
          <p className="mt-1 text-sm text-stone-500">Auto-refreshing every 5 seconds.</p>
        </div>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {npcs.map((npc) => (
          <Link
            key={npc.id}
            to={`/npc/${npc.id}`}
            className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm transition hover:border-stone-300 hover:shadow"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-stone-950">{npc.name}</h2>
                <p className="text-xs text-stone-500">{npc.id}</p>
              </div>
              <EmotionBadge emotion={npc.emotion} />
            </div>

            <div className="mt-3 inline-flex rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-teal-700">
              {npc.fsm_state}
            </div>

            <div className="mt-5">
              <ReputationBar value={npc.reputation} />
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md bg-stone-50 p-3">
                <div className="text-xs text-stone-500">Memories</div>
                <div className="mt-1 text-xl font-semibold text-stone-950">{npc.memory_count}</div>
              </div>
              <div className="rounded-md bg-stone-50 p-3">
                <div className="text-xs text-stone-500">Relationships</div>
                <div className="mt-1 text-xl font-semibold text-stone-950">{npc.relationship_count}</div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
