// app/components/VideoCard.tsx
"use client";

import { useState } from "react";
import type { Video } from "../types";

type VideoCardProps = {
  video: Video;
  onSave?: (updated: Video) => void;
  onPublish?: (videoId: string) => void;
};

export default function VideoCard({ video, onSave, onPublish }: VideoCardProps) {
  const [caption, setCaption] = useState(video.caption);
  const [scheduledAt, setScheduledAt] = useState(video.scheduledAt ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);

    const updated: Video = {
      ...video,
      caption,
      scheduledAt: scheduledAt || undefined,
    };

    // FRONTEND ONLY – you wire the backend
    try {
      if (onSave) {
        await onSave(updated);
      }
    } finally {
      setSaving(false);
    }
  };

  const handlePublishClick = async () => {
    if (onPublish) {
      await onPublish(video.id);
    }
  };

  const statusLabel = video.status.charAt(0).toUpperCase() + video.status.slice(1);

  return (
    <div className="card video-card">
      <div className="video-thumb">
        {/* video.url should be playable – you decide the backend path */}
        <video src={video.url} controls width={260} />
      </div>

      <div className="video-meta">
        <p className="video-filename">{video.filename}</p>
        <span className={`status status-${video.status}`}>{statusLabel}</span>
      </div>

      <label className="field">
        <span>Caption</span>
        <textarea
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          rows={3}
        />
      </label>

      <label className="field">
        <span>Schedule (optional)</span>
        <input
          type="datetime-local"
          value={scheduledAt}
          onChange={(e) => setScheduledAt(e.target.value)}
        />
      </label>

      <div className="video-actions">
        <button onClick={handleSave} disabled={saving} className="btn primary">
          {saving ? "Saving..." : "Save"}
        </button>
        <button onClick={handlePublishClick} className="btn outline">
          Publish now
        </button>
      </div>
    </div>
  );
}
