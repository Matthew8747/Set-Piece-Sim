import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // shared-types ships TypeScript source; Next transpiles it in-place.
  transpilePackages: ["@restart/shared-types"],
};

export default nextConfig;
