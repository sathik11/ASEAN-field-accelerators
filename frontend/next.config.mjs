/** @type {import('next').NextConfig} */
const nextConfig = {
  // Ensure that Next.js can handle static assets correctly
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
