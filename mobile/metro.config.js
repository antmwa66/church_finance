const { getDefaultConfig } = require('expo/metro-config');
const config = getDefaultConfig(__dirname);

config.resolver.sourceExts = config.resolver.sourceExts.filter((ext: string) => ext !== 'web.js');
config.resolver.blockList = [/node_modules\/.*\/node_modules\/react-dom\/.*/];

module.exports = config;