import type { Metadata } from "next";
import "bootstrap/dist/css/bootstrap.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "DeepVerify — Claim Investigations",
  description:
    "Investigate factual assertions, inspect source evidence, and build a reviewed research memory.",
  keywords: ["claims", "evidence", "investigation", "research"],
  openGraph: {
    title: "DeepVerify — Claim Investigations",
    description: "Evidence, uncertainty, and reviewed research memory",
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
