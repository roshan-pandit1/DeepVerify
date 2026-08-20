import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DeepVerify — Multi-Modal Video Authenticity Engine",
  description:
    "Professional deepfake and cheapfake detection using C2PA cryptographic verification, computer vision, audio analysis, and OSINT reverse image search.",
  keywords: ["deepfake detection", "video authenticity", "C2PA", "cheapfake", "forensics"],
  openGraph: {
    title: "DeepVerify — Video Authenticity Engine",
    description: "AI-powered forensic analysis for video authenticity verification",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, backgroundColor: "#ffffff" }}>
        {children}
      </body>
    </html>
  );
}
