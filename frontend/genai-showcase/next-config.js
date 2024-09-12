/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "export",
  swcMinify: true,
  experimental: {
    appDir: true,
  },
};

module.exports = nextConfig;
