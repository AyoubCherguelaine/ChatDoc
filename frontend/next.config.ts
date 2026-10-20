import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  /* config options here */
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
