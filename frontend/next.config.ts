import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The frontend is an independent package; root manifests are retained separately.
  turbopack: { root: __dirname },
  outputFileTracingRoot: __dirname,
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/static/**",
      },
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
  // Allow cross-origin for static assets during dev
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
        ],
      },
    ];
  },
};

export default nextConfig;
