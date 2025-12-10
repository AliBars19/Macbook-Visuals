// app/types.ts

export type VideoStatus = "draft" | "scheduled" | "published";

export interface Video {
  id: string;           // unique ID from your backend
  filename: string;     // original file name
  url: string;          // URL where the video can be played (you decide)
  caption: string;
  scheduledAt?: string; // ISO string, e.g. "2025-12-10T18:30"
  status: VideoStatus;
}
