/** @type {import('next').NextConfig} */
const isWin = process.platform === "win32";

const nextConfig = {
  reactStrictMode: true,
  // No Windows, o watcher nativo por vezes deixa o .next a meio → chunks em falta (ex.: 499.js).
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: isWin ? 800 : false,
        aggregateTimeout: 500,
        ignored: /node_modules/,
      };
    }
    return config;
  },
};

module.exports = nextConfig;
