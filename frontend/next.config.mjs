/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  async rewrites() {
    return [
      {
        source: '/health',
        destination: 'http://127.0.0.1:8000/health',
      },
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
      {
        source: '/static/:path*',
        destination: 'http://127.0.0.1:8000/static/:path*',
      },
    ];
  },
};

export default nextConfig;
