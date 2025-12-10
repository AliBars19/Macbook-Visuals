"use client";

import { useEffect, useState } from "react";
import type { Video } from "../types";
import VideoCard from "../components/VideoCard";

export default function Dashboard() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        setLoading(true);
        setError(null);

        const res = await fetch("/api/videos");
        if (!res.ok) throw new Error("Failed to fetch videos");

        const data: Video[] = await res.json();
        setVideos(data);
      } catch (err: any) {
        setError(err.message ?? "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchVideos();
  }, []);

  const handleSave = async (updated: Video) => {
    const res = await fetch(`/api/videos/${updated.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        caption: updated.caption,
        scheduledAt: updated.scheduledAt,
      }),
    });

    if (!res.ok) {
      console.error("Failed to save video");
      return;
    }

    setVideos((prev) =>
      prev.map((v) => (v.id === updated.id ? updated : v))
    );
  };

  const handlePublish = async (videoId: string) => {
    const res = await fetch(`/api/videos/${videoId}/publish`, {
      method: "POST",
    });

    if (!res.ok) {
      console.error("Failed to publish video");
      return;
    }

    setVideos((prev) =>
      prev.map((v) =>
        v.id === videoId ? { ...v, status: "published" } : v
      )
    );
  };

  return (
    <main className="dashboard">
      <h1 className="title">Your Video Dashboard</h1>

      {loading && <p>Loading videos...</p>}
      {error && <p className="error">Error: {error}</p>}

      {!loading && videos.length === 0 && (
        <p>No videos yet. Upload or send some from your pipeline.</p>
      )}

      <div className="grid">
        {videos.map((video) => (
          <VideoCard
            key={video.id}
            video={video}
            onSave={handleSave}
            onPublish={handlePublish}
          />
        ))}
      </div>
    </main>
  );
}
