import React from "react";

function reputationColor(value) {
  if (value > 25) return "bg-green-500";
  if (value < -25) return "bg-red-500";
  return "bg-gray-400";
}

export default function ReputationBar({ value = 0 }) {
  const clamped = Math.max(-100, Math.min(100, value));
  const width = `${Math.abs(clamped) / 2}%`;
  const left = clamped < 0 ? `${50 - Math.abs(clamped) / 2}%` : "50%";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-stone-500">
        <span>-100</span>
        <span className="font-medium text-stone-700">{clamped}</span>
        <span>+100</span>
      </div>
      <div className="relative h-3 rounded-full bg-stone-200">
        <div className="absolute left-1/2 top-0 h-3 w-px bg-stone-500" />
        <div
          className={`absolute top-0 h-3 rounded-full ${reputationColor(clamped)}`}
          style={{ left, width }}
        />
      </div>
    </div>
  );
}
