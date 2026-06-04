import React, { useCallback, useEffect, useRef, useState } from "react";

// Village zone definitions matching backend world.py
const ZONES = {
  guard_post:   { x: -30, z: 30,  radius: 10, color: "#ef4444", label: "Guard Post" },
  market_stall: { x: 30,  z: 30,  radius: 12, color: "#f59e0b", label: "Market" },
  town_square:  { x: 0,   z: 0,   radius: 15, color: "#10b981", label: "Town Square" },
  tavern:       { x: -30, z: -30, radius: 10, color: "#8b5cf6", label: "Tavern" },
  church:       { x: 30,  z: -30, radius: 10, color: "#3b82f6", label: "Church" },
  smithy:       { x: 0,   z: -50, radius: 8,  color: "#f97316", label: "Smithy" },
};

const ENTITY_COLORS = {
  npc: "#14b8a6",
  player: "#f43f5e",
  object: "#a78bfa",
};

const WORLD_BOUNDS = { minX: -65, maxX: 65, minZ: -65, maxZ: 65 };

export default function WorldMap({
  entities = [],
  zones = {},
  selectedNpcId = null,
  fovData = null,
  onEntityClick = () => {},
  onMapClick = () => {},
  soundRipples = [],
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [canvasSize, setCanvasSize] = useState({ w: 600, h: 600 });

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const obs = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        const h = Math.max(400, Math.min(w, 700));
        setCanvasSize({ w, h });
      }
    });
    obs.observe(container);
    return () => obs.disconnect();
  }, []);

  // Convert world coordinates to canvas coordinates
  const worldToCanvas = useCallback((wx, wz) => {
    const { w, h } = canvasSize;
    const pad = 30;
    const rangeX = WORLD_BOUNDS.maxX - WORLD_BOUNDS.minX;
    const rangeZ = WORLD_BOUNDS.maxZ - WORLD_BOUNDS.minZ;
    const cx = pad + ((wx - WORLD_BOUNDS.minX) / rangeX) * (w - 2 * pad);
    const cy = pad + ((WORLD_BOUNDS.maxZ - wz) / rangeZ) * (h - 2 * pad); // flip Z
    return { cx, cy };
  }, [canvasSize]);

  const canvasToWorld = useCallback((cx, cy) => {
    const { w, h } = canvasSize;
    const pad = 30;
    const rangeX = WORLD_BOUNDS.maxX - WORLD_BOUNDS.minX;
    const rangeZ = WORLD_BOUNDS.maxZ - WORLD_BOUNDS.minZ;
    const wx = WORLD_BOUNDS.minX + ((cx - pad) / (w - 2 * pad)) * rangeX;
    const wz = WORLD_BOUNDS.maxZ - ((cy - pad) / (h - 2 * pad)) * rangeZ;
    return { wx, wz };
  }, [canvasSize]);

  const worldToCanvasRadius = useCallback((worldRadius) => {
    const { w } = canvasSize;
    const pad = 30;
    const rangeX = WORLD_BOUNDS.maxX - WORLD_BOUNDS.minX;
    return (worldRadius / rangeX) * (w - 2 * pad);
  }, [canvasSize]);

  // Canvas click handler
  const handleCanvasClick = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const sy = (e.clientY - rect.top) * (canvas.height / rect.height);

    // Check if clicked on an entity
    for (const entity of entities) {
      const { cx, cy } = worldToCanvas(entity.x, entity.z);
      const dist = Math.sqrt((sx - cx) ** 2 + (sy - cy) ** 2);
      if (dist < 12) {
        onEntityClick(entity);
        return;
      }
    }

    // Otherwise: map click (move player)
    const { wx, wz } = canvasToWorld(sx, sy);
    onMapClick(wx, wz);
  }, [entities, worldToCanvas, canvasToWorld, onEntityClick, onMapClick]);

  // Draw everything
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasSize.w * dpr;
    canvas.height = canvasSize.h * dpr;
    canvas.style.width = `${canvasSize.w}px`;
    canvas.style.height = `${canvasSize.h}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, canvasSize.w, canvasSize.h);

    // Background
    ctx.fillStyle = "#1a1a2e";
    ctx.fillRect(0, 0, canvasSize.w, canvasSize.h);

    // Grid lines
    ctx.strokeStyle = "rgba(255,255,255,0.05)";
    ctx.lineWidth = 0.5;
    for (let wx = -60; wx <= 60; wx += 10) {
      const { cx } = worldToCanvas(wx, 0);
      ctx.beginPath();
      ctx.moveTo(cx, 0);
      ctx.lineTo(cx, canvasSize.h);
      ctx.stroke();
    }
    for (let wz = -60; wz <= 60; wz += 10) {
      const { cy } = worldToCanvas(0, wz);
      ctx.beginPath();
      ctx.moveTo(0, cy);
      ctx.lineTo(canvasSize.w, cy);
      ctx.stroke();
    }

    // Draw zones
    for (const [zoneId, zoneDef] of Object.entries(ZONES)) {
      const { cx, cy } = worldToCanvas(zoneDef.x, zoneDef.z);
      const r = worldToCanvasRadius(zoneDef.radius);

      // Zone area
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = zoneDef.color + "18";
      ctx.fill();
      ctx.strokeStyle = zoneDef.color + "40";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Zone label
      ctx.fillStyle = zoneDef.color + "90";
      ctx.font = "bold 10px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(zoneDef.label, cx, cy + r + 14);
    }

    // Draw FOV cone for selected NPC
    if (fovData && selectedNpcId) {
      const { cx, cy } = worldToCanvas(fovData.x, fovData.z);
      const visionR = worldToCanvasRadius(fovData.vision_range);
      const hearingR = worldToCanvasRadius(fovData.hearing_range);
      const facingRad = (-fovData.facing_angle + 90) * (Math.PI / 180);
      const halfFov = (fovData.vision_fov / 2) * (Math.PI / 180);

      // Hearing radius (dashed circle)
      ctx.beginPath();
      ctx.arc(cx, cy, hearingR, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(251, 191, 36, 0.25)";
      ctx.lineWidth = 1;
      ctx.setLineDash([6, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Vision cone
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, visionR, facingRad - halfFov, facingRad + halfFov);
      ctx.closePath();
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, visionR);
      grad.addColorStop(0, "rgba(20, 184, 166, 0.30)");
      grad.addColorStop(1, "rgba(20, 184, 166, 0.03)");
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.strokeStyle = "rgba(20, 184, 166, 0.5)";
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Draw sound ripples
    for (const ripple of soundRipples) {
      const { cx, cy } = worldToCanvas(ripple.x, ripple.z);
      const maxR = worldToCanvasRadius(ripple.radius || 30);
      const progress = ripple.progress || 0;
      const r = maxR * progress;
      const alpha = Math.max(0, 0.4 * (1 - progress));

      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(251, 191, 36, ${alpha})`;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Draw entities
    for (const entity of entities) {
      const { cx, cy } = worldToCanvas(entity.x, entity.z);
      const isSelected = entity.id === selectedNpcId;
      const color = ENTITY_COLORS[entity.entity_type] || "#94a3b8";
      const radius = entity.entity_type === "player" ? 8 : 6;

      // Selection glow
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(cx, cy, radius + 6, 0, Math.PI * 2);
        ctx.fillStyle = color + "30";
        ctx.fill();
        ctx.strokeStyle = color + "80";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Entity dot
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = "#1a1a2e";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Facing direction arrow (for NPCs and player)
      if (entity.entity_type === "npc" || entity.entity_type === "player") {
        const angle = (-entity.facing_angle + 90) * (Math.PI / 180);
        const arrowLen = radius + 6;
        const ax = cx + Math.cos(angle) * arrowLen;
        const ay = cy - Math.sin(angle) * arrowLen;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(angle) * radius, cy - Math.sin(angle) * radius);
        ctx.lineTo(ax, ay);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Entity label
      ctx.fillStyle = "#e2e8f0";
      ctx.font = `${isSelected ? "bold " : ""}10px Inter, sans-serif`;
      ctx.textAlign = "center";
      const label = entity.entity_type === "player" ? "Player" : entity.id.replace(/_\d+$/, "");
      ctx.fillText(label, cx, cy - radius - 6);
    }

    // Legend
    const legendX = 12;
    let legendY = canvasSize.h - 60;
    ctx.font = "9px Inter, sans-serif";
    for (const [type, color] of Object.entries(ENTITY_COLORS)) {
      ctx.beginPath();
      ctx.arc(legendX + 5, legendY, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.fillStyle = "#94a3b8";
      ctx.textAlign = "left";
      ctx.fillText(type.charAt(0).toUpperCase() + type.slice(1), legendX + 14, legendY + 3);
      legendY += 16;
    }
  }, [canvasSize, entities, zones, selectedNpcId, fovData, soundRipples, worldToCanvas, worldToCanvasRadius]);

  return (
    <div ref={containerRef} className="w-full">
      <canvas
        ref={canvasRef}
        onClick={handleCanvasClick}
        className="w-full rounded-lg cursor-crosshair"
        style={{ height: `${canvasSize.h}px` }}
      />
    </div>
  );
}
