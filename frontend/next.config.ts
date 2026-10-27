import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // OCR can take several minutes before returning a response.
    proxyTimeout: 600_000,
  },
  async rewrites() {
    const backendUrl = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  // Instant navigation (cacheComponents + partialPrefetching) is disabled:
  // the app uses a client-side auth guard, and the `instant` segment config
  // is not allowed in Client Components.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
