/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_INTERNAL_URL || 'http://127.0.0.1:8000';
const nextConfig = {
  output: 'standalone',
  reactStrictMode: false,

  async rewrites() {
    return [
      {
        source: '/health',
        destination: `${backend}/api/v1/health`,
      },
      {
        source: '/api/:path*',
        destination: `${backend}/api/:path*`,
      },
      {
        source: '/static/:path*',
        destination: `${backend}/static/:path*`,
      },
    ];
  },
};

export default nextConfig;
