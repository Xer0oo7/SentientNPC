import React from "react";

const PERCEPTION_TYPE_STYLES = {
  vision: { dot: "bg-teal-400", badge: "bg-teal-900/50 text-teal-300", icon: "👁" },
  hearing: { dot: "bg-amber-400", badge: "bg-amber-900/50 text-amber-300", icon: "👂" },
};

export default function PerceptionPanel({
  selectedNpcId = null,
  config = null,
  nearbyEntities = [],
  recentEvents = [],
}) {
  if (!selectedNpcId) {
    return (
      <div className="rounded-lg border border-stone-200 bg-white p-6 text-center text-sm text-stone-400">
        Click an NPC on the map to view its perception state
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* NPC Info Header */}
      <div className="rounded-lg border border-stone-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">
          {selectedNpcId}
          <span className="ml-2 text-xs font-normal text-stone-400">Perception Config</span>
        </h3>
        {config && (
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-md bg-teal-50 p-2.5 text-center">
              <div className="text-xs text-teal-600 mb-0.5">Vision Range</div>
              <div className="text-lg font-semibold text-teal-700">{config.vision_range}m</div>
            </div>
            <div className="rounded-md bg-teal-50 p-2.5 text-center">
              <div className="text-xs text-teal-600 mb-0.5">FOV</div>
              <div className="text-lg font-semibold text-teal-700">{config.vision_fov}°</div>
            </div>
            <div className="rounded-md bg-amber-50 p-2.5 text-center">
              <div className="text-xs text-amber-600 mb-0.5">Hearing</div>
              <div className="text-lg font-semibold text-amber-700">{config.hearing_range}m</div>
            </div>
          </div>
        )}
      </div>

      {/* Nearby Entities */}
      <div className="rounded-lg border border-stone-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-stone-900 mb-2">
          Nearby Entities
          <span className="ml-2 text-xs font-normal text-stone-400">
            {nearbyEntities.length} detected
          </span>
        </h3>
        {nearbyEntities.length === 0 ? (
          <p className="text-xs text-stone-400">No entities in range</p>
        ) : (
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {nearbyEntities.map((e) => (
              <div
                key={e.id}
                className="flex items-center justify-between rounded-md bg-stone-50 px-3 py-1.5 text-xs"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-stone-800">{e.id}</span>
                  <span className="text-stone-400">{e.entity_type}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-stone-500">{e.distance}m</span>
                  {e.in_vision && (
                    <span className="rounded bg-teal-100 text-teal-700 px-1.5 py-0.5 text-[10px] font-medium">
                      👁 Vision
                    </span>
                  )}
                  {e.in_hearing && (
                    <span className="rounded bg-amber-100 text-amber-700 px-1.5 py-0.5 text-[10px] font-medium">
                      👂 Hearing
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Perception Events */}
      <div className="rounded-lg border border-stone-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-stone-900 mb-2">
          Perception Events
          <span className="ml-2 text-xs font-normal text-stone-400">
            last {recentEvents.length}
          </span>
        </h3>
        {recentEvents.length === 0 ? (
          <p className="text-xs text-stone-400">No perception events yet. Start the simulation and move entities nearby.</p>
        ) : (
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {recentEvents.map((evt, i) => {
              const style = PERCEPTION_TYPE_STYLES[evt.perception_type] || PERCEPTION_TYPE_STYLES.vision;
              return (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded-md bg-stone-50 px-3 py-1.5 text-xs"
                >
                  <span className={`mt-0.5 h-2 w-2 rounded-full flex-shrink-0 ${style.dot}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${style.badge}`}>
                        {style.icon} {evt.perception_type}
                      </span>
                      <span className="text-stone-400">tick {evt.tick}</span>
                    </div>
                    <div className="text-stone-600 mt-0.5 truncate">
                      {evt.perception_type === "vision"
                        ? `Spotted ${evt.target_id} at ${evt.distance}m`
                        : `Heard ${evt.sound_type} from ${evt.source_id} (${evt.intensity?.toFixed(2)} intensity)`
                      }
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
