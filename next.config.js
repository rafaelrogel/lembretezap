/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Fast Refresh and HMR are enabled by default; keep webpack optimizations for fast rebuilds.
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: false,
        aggregateTimeout: 300,
        ignored: /node_modules/,
      };
    }
    return config;
  },
};

module.exports = nextConfig;
