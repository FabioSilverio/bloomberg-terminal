/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  experimental: {
    optimizePackageImports: ['@tanstack/react-query', 'zustand']
  }
};

export default nextConfig;
