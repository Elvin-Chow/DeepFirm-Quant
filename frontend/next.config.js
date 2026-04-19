/** @type {import('next').NextConfig} */
const path = require('path');

const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // Ensure alias object exists
    if (!config.resolve.alias) {
      config.resolve.alias = {};
    }

    // Set the @ alias to project root
    config.resolve.alias['@'] = path.resolve(__dirname);

    // Also add the project root to module search paths
    config.resolve.modules = [
      path.resolve(__dirname),
      ...(config.resolve.modules || []),
    ];

    return config;
  },
};

module.exports = nextConfig;
