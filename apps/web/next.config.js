/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://api:8000/api/:path*'
      },
      {
        source: '/ask',
        destination: 'http://api:8000/ask'
      }
    ]
  }
}

module.exports = nextConfig