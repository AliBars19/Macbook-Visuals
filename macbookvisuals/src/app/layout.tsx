// app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import Navbar from "./components/Navbar";

export const metadata: Metadata = {
  title: "MacbookVisuals Dashboard",
  description: "Local dashboard for managing TikTok videos and captions",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <div className="page-container">{children}</div>
      </body>
    </html>
  );
}
