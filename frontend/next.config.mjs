/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "moltbook.com" },
    ],
  },
};

export default nextConfig;
