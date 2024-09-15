/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  swcMinify: true,
  experimental: {
    appDir: true,
  },
};

module.exports = nextConfig;
