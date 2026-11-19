
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Traces only the node_modules this app actually needs into
  // .next/standalone, so the Docker runtime image doesn't need a full
  // `npm install` - see apps/frontend/Dockerfile.
  output: "standalone",
};

export default nextConfig;
