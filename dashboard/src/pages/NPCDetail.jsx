import {
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  PointElement,
  RadialLinearScale,
  Tooltip,
} from "chart.js";
import { useEffect, useMemo, useState } from "react";
import { Radar } from "react-chartjs-2";
import { Link, useParams } from "react-router-dom";

import { getNPCAnalytics } from "../api/client.js";
import EmotionBadge from "../components/EmotionBadge.jsx";
import ReputationBar from "../components/ReputationBar.jsx";

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

function importanceClass(value) {
  if (value >= 0.7) return "bg-red-100 text-red-800";
  if (value >= 0.4) return "bg-yellow-100 text-yellow-900";
  return "bg-gray-100 text-gray-800";
}

export default function NPCDetail() {
  const { id } = useParams();
  const [npc, setNpc] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const data = await getNPCAnalytics(id);
        if (mounted) {
          setNpc(data);
          setError("");
        }
      } catch (err) {
        if (mounted) setError("Unable to load NPC analytics.");
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [id]);

  const radarData = useMemo(() => {
    const personality = npc?.personality || {};
    const labels = ["aggressive", "friendly", "greedy", "bravery", "curiosity", "loyalty"];
    return {
      labels,
      datasets: [
        {
          label: "Personality",
          data: labels.map((key) => personality[key] || 0),
          backgroundColor: "rgba(20, 184, 166, 0.18)",
          borderColor: "rgb(13, 148, 136)",
          borderWidth: 2,
          pointBackgroundColor: "rgb(13, 148, 136)",
        },
      ],
    };
  }, [npc]);

  const radarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        min: 0,
        max: 100,
        ticks: { stepSize: 20 },
        pointLabels: { font: { size: 12 } },
      },
    },
    plugins: {
      legend: { display: false },
    },
  };

  if (error) {
    return <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>;
  }

  if (!npc) {
    return <div className="text-sm text-stone-500">Loading NPC state...</div>;
  }

  return (
    <section className="space-y-5">
      <Link to="/" className="text-sm font-medium text-teal-700 hover:text-teal-900">
        Back to overview
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-stone-950">{npc.name}</h1>
          <p className="mt-1 text-sm text-stone-500">{npc.id}</p>
        </div>
        <EmotionBadge emotion={npc.emotion} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-stone-950">Personality</h2>
          <div className="mt-4 h-72">
            <Radar data={radarData} options={radarOptions} />
          </div>
        </div>

        <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-stone-950">Reputation</h2>
          <div className="mt-5">
            <ReputationBar value={npc.reputation} />
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <div className="rounded-md bg-stone-50 p-3">
              <div className="text-xs text-stone-500">Emotion</div>
              <div className="mt-2">
                <EmotionBadge emotion={npc.emotion} />
              </div>
            </div>
            <div className="rounded-md bg-stone-50 p-3">
              <div className="text-xs text-stone-500">Memories</div>
              <div className="mt-1 text-xl font-semibold text-stone-950">{npc.memories.length}</div>
            </div>
            <div className="rounded-md bg-stone-50 p-3">
              <div className="text-xs text-stone-500">Recent Dialogue</div>
              <div className="mt-1 text-xl font-semibold text-stone-950">{npc.recent_dialogue_count}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-stone-200 bg-white shadow-sm">
        <div className="border-b border-stone-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-stone-950">Memory Log</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-stone-200 text-sm">
            <thead className="bg-stone-50 text-left text-xs uppercase text-stone-500">
              <tr>
                <th className="px-4 py-3">Event</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Importance</th>
                <th className="px-4 py-3">Longterm</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {npc.memories.map((memory) => (
                <tr key={memory.id}>
                  <td className="px-4 py-3 font-medium text-stone-900">{memory.event_type}</td>
                  <td className="px-4 py-3 text-stone-700">{memory.description}</td>
                  <td className="px-4 py-3 text-stone-500">{memory.location || "-"}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${importanceClass(memory.importance)}`}>
                      {memory.importance}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-stone-600">{memory.is_longterm ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-stone-950">Relationships</h2>
          <div className="mt-3 divide-y divide-stone-100">
            {npc.relationships.map((relationship) => (
              <div key={relationship.player_id} className="flex items-center justify-between gap-3 py-3 text-sm">
                <div>
                  <div className="font-medium text-stone-900">{relationship.player_id}</div>
                  <div className="text-xs text-stone-500">{relationship.label}</div>
                </div>
                <div className="font-semibold text-stone-950">{relationship.score}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-stone-950">Recent Dialogue History</h2>
          <div className="mt-3 space-y-3">
            {npc.recent_dialogue.map((entry) => (
              <div key={entry.id} className="rounded-md bg-stone-50 p-3 text-sm">
                <div className="text-xs text-stone-500">{entry.player_id}</div>
                <div className="mt-1 text-stone-800">Player: {entry.player_message}</div>
                <div className="mt-1 font-medium text-stone-950">NPC: {entry.npc_response}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
