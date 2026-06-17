import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Workspace packages ship TypeScript source; Next transpiles them in-place.
  transpilePackages: ["@restart/shared-types", "@restart/pitch-kit"],
};

export default nextConfig;
