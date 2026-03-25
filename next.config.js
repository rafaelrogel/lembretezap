/** @type {import('next').NextConfig} */
const isStaticExport = process.env.STATIC_EXPORT === "1";

const nextConfig = {
  // Só para ZIP/preview estático: STATIC_EXPORT=1 npm run build:static
  // Na Vercel use o build normal (sem esta env) — senão o deploy dá 404.
  ...(isStaticExport
    ? { output: "export", images: { unoptimized: true } }
    : {}),
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
