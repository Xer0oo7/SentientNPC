import React from "react";

import SimulationControls from "../components/SimulationControls.jsx";
import QueueVisualization from "../components/QueueVisualization.jsx";
import EventFeed from "../components/EventFeed.jsx";

export default function Simulation() {
  return (
    <section className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-stone-950">Simulation</h1>
        <p className="mt-1 text-sm text-stone-500">
          Control the tick engine, inject events, and watch NPC priority queues process in real time.
        </p>
      </div>

      {/* Engine controls + injection */}
      <SimulationControls />

      {/* NPC Queue visualization */}
      <QueueVisualization />

      {/* Live event feed */}
      <EventFeed maxEvents={100} />
    </section>
  );
}
