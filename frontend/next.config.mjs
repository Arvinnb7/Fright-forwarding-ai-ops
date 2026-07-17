/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output so the Docker image ships a self-contained production
  // server (node server.js) instead of running the dev server.
  output: "standalone",
};

export default nextConfig;
