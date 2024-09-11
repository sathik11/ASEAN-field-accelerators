/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  reactStrictMode: true,
  swcMinify: true,
  // Ensure that Next.js can handle static assets correctly
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
