import type { UserConfigExport } from '@tarojs/cli';

// Dev 环境覆盖；与 config/index.ts 浅 merge。
const config: UserConfigExport = {
  logger: {
    quiet: false,
    stats: true,
  },
  mini: {},
  h5: {},
};

export default config;
