"use client";

import { useState } from "react";

type UploadStatus = "idle" | "uploading" | "done" | "error";

export default function UploadPage() {
  const [files, setFiles] = useState<FileList | null>(null);
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [message, setMessage] = useState("");

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFiles(e.target.files);
    setStatus("idle");
    setMessage("");
  };

  const handleUpload = async () => {
    if (!files || files.length === 0) return;

    setStatus("uploading");
    setMessage("");

    try {
      for (const file of Array.from(files)) {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch("/api/upload", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          throw new Error(`Failed to upload ${file.name}`);
        }
      }

      setStatus("done");
      setMessage("Upload complete! Check your dashboard.");
    } catch (err: any) {
      console.error(err);
      setStatus("error");
      setMessage(err.message ?? "Upload failed");
    }
  };

  return (
    <main className="upload-page">
      <h1 className="title">Upload Videos</h1>

      <div className="card upload-card">
        <label className="field">
          <span>Select one or more video files</span>
          <input type="file" multiple onChange={handleFileChange} />
        </label>

        {files && files.length > 0 && (
          <div className="selected-files">
            <h3>Selected files:</h3>
            <ul>
              {Array.from(files).map((file) => (
                <li key={file.name}>{file.name}</li>
              ))}
            </ul>
          </div>
        )}

        <button
          className="btn primary"
          onClick={handleUpload}
          disabled={!files || files.length === 0 || status === "uploading"}
        >
          {status === "uploading" ? "Uploading..." : "Upload"}
        </button>

        {message && (
          <p className={status === "error" ? "error" : "success"}>{message}</p>
        )}
      </div>
    </main>
  );
}
