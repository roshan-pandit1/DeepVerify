"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import type { TimelineEvent } from "../../lib/api";

interface VideoTimelineProps {
  videoPath: string;   // Public URL served by FastAPI
  events: TimelineEvent[];
  duration: number;
}

export function VideoTimeline({ videoPath, events, duration }: VideoTimelineProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(duration || 1);
  const [activeEvent, setActiveEvent] = useState<TimelineEvent | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // Update canvas timeline on time change
  const drawTimeline = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Track background
    ctx.fillStyle = "#f1f5f9";
    ctx.beginPath();
    ctx.roundRect(0, H / 2 - 3, W, 6, 3);
    ctx.fill();

    // Filled track
    const prog = (currentTime / videoDuration) * W;
    ctx.fillStyle = "#0ea5e9";
    ctx.beginPath();
    ctx.roundRect(0, H / 2 - 3, prog, 6, 3);
    ctx.fill();

    // Event dots
    events.forEach((ev) => {
      if (!ev.timestamp) return;
      const x = (ev.timestamp / videoDuration) * W;
      const isAnomaly = ev.is_anomaly;
      ctx.beginPath();
      ctx.arc(x, H / 2, isAnomaly ? 6 : 4, 0, 2 * Math.PI);
      ctx.fillStyle = isAnomaly ? "#f43f5e" : "#10b981";
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.stroke();
    });

    // Playhead
    ctx.fillStyle = "#0284c7";
    ctx.beginPath();
    ctx.arc(prog, H / 2, 8, 0, 2 * Math.PI);
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 3;
    ctx.stroke();
  }, [currentTime, videoDuration, events]);

  useEffect(() => {
    drawTimeline();
  }, [drawTimeline]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const onTime = () => {
      setCurrentTime(video.currentTime);
      // Check for nearby event
      const nearby = events.find(
        (ev) => Math.abs(ev.timestamp - video.currentTime) < 1.5 && ev.is_anomaly
      );
      setActiveEvent(nearby ?? null);
    };
    const onMeta = () => setVideoDuration(video.duration || duration);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    video.addEventListener("timeupdate", onTime);
    video.addEventListener("loadedmetadata", onMeta);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    return () => {
      video.removeEventListener("timeupdate", onTime);
      video.removeEventListener("loadedmetadata", onMeta);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
    };
  }, [events, duration]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const ratio = x / canvas.offsetWidth;
    video.currentTime = ratio * videoDuration;
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const anomalyEvents = events.filter((e) => e.is_anomaly);

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
        <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          📹 Video Player & Anomaly Timeline
        </h2>
        {anomalyEvents.length > 0 && (
          <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--rose-500)", fontWeight: 500 }}>
            {anomalyEvents.length} suspicious frame{anomalyEvents.length !== 1 ? "s" : ""} detected
          </p>
        )}
      </div>

      {/* Video */}
      <video
        ref={videoRef}
        src={videoPath}
        controls
        style={{ width: "100%", display: "block", maxHeight: "420px", background: "#000" }}
        crossOrigin="anonymous"
      />

      {/* Timeline */}
      <div style={{ padding: "16px 24px" }}>
        <canvas
          ref={canvasRef}
          width={900}
          height={40}
          onClick={handleCanvasClick}
          style={{
            width: "100%", height: "40px", cursor: "pointer",
            display: "block",
          }}
        />
        <div style={{
          display: "flex", justifyContent: "space-between",
          fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "6px",
          fontFamily: "JetBrains Mono, monospace",
        }}>
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(videoDuration)}</span>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", gap: "16px", marginTop: "12px" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.78rem", color: "var(--text-muted)" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#f43f5e", display: "inline-block" }} />
            Suspicious frame
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.78rem", color: "var(--text-muted)" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
            Normal face detected
          </span>
        </div>
      </div>

      {/* Active anomaly callout */}
      {activeEvent && (
        <div style={{
          margin: "0 24px 20px",
          padding: "12px 16px",
          background: "var(--rose-50)",
          border: "1px solid var(--rose-100)",
          borderRadius: "var(--radius-md)",
          display: "flex", alignItems: "center", gap: "10px",
        }}>
          <span style={{ fontSize: "1.2rem" }}>⚠️</span>
          <div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem", color: "#9f1239" }}>
              Anomaly at {formatTime(activeEvent.timestamp)}
            </p>
            <p style={{ margin: "2px 0 0", fontSize: "0.78rem", color: "var(--text-muted)" }}>
              {activeEvent.label} — Score: {activeEvent.score?.toFixed(1)}%
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
