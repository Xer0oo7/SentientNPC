import React from "react";

const emotionClasses = {
  happy: "bg-green-100 text-green-800 ring-green-200",
  angry: "bg-red-100 text-red-800 ring-red-200",
  fearful: "bg-yellow-100 text-yellow-900 ring-yellow-200",
  sad: "bg-blue-100 text-blue-800 ring-blue-200",
  neutral: "bg-gray-100 text-gray-800 ring-gray-200",
  excited: "bg-purple-100 text-purple-800 ring-purple-200",
};

export default function EmotionBadge({ emotion }) {
  const key = emotion || "neutral";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${emotionClasses[key] || emotionClasses.neutral}`}>
      {key}
    </span>
  );
}
