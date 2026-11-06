import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // This app has no imports outside its directory; keep standalone/server.js at the app root.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
