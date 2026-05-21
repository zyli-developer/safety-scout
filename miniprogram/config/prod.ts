import type { UserConfigExport } from '@tarojs/cli';

// Prod 环境覆盖；与 config/index.ts 浅 merge。
const config: UserConfigExport = {
  mini: {},
  h5: {
    /**
     * 若要为 H5 构建分析包体积：
     *   1. npm i webpack-bundle-analyzer
     *   2. 在 webpackChain 里加 BundleAnalyzerPlugin
     *   3. taro build --type h5 --watch
     */
  },
};

export default config;
