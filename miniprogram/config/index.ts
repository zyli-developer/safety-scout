import { defineConfig, type UserConfigExport } from '@tarojs/cli';

import devConfig from './dev';
import prodConfig from './prod';

// https://docs.taro.zone/docs/config —— Taro 4 项目配置入口
// dev / prod 通过 NODE_ENV 切到对应 override，浅 merge
export default defineConfig(async (merge, { command, mode }) => {
  const baseConfig: UserConfigExport = {
    projectName: 'safety-scout-miniprogram',
    date: '2026-5-19',
    designWidth: 750,
    deviceRatio: {
      640: 2.34 / 2,
      750: 1,
      375: 2,
      828: 1.81 / 2,
    },
    sourceRoot: 'src',
    outputRoot: 'dist',
    plugins: [],
    defineConstants: {
      // 把 build 时的 shell env var TARO_API_BASE_URL 通过 DefinePlugin 注入到
      // 客户端代码（src/config.ts 中的 process.env.API_BASE_URL 引用会被替换）。
      // 见 src/config.ts 顶部说明为什么不用 NODE_ENV 切换。
      'process.env.API_BASE_URL': JSON.stringify(
        process.env.TARO_API_BASE_URL || 'https://api.example.com',
      ),
    },
    copy: {
      patterns: [],
      options: {},
    },
    framework: 'react',
    compiler: 'webpack5',
    cache: {
      enable: false, // CI 跑全量；本地开发想加速可手动开
    },
    mini: {
      postcss: {
        pxtransform: {
          enable: true,
          config: {},
        },
        cssModules: {
          // 我们组件全部用 *.module.scss + import styles from '...'，
          // 必须开 cssModules 才能让 styles.foo 解析到正确类名
          enable: true,
          config: {
            namingPattern: 'module',
            generateScopedName: '[name]__[local]___[hash:base64:5]',
          },
        },
      },
    },
    h5: {
      publicPath: '/',
      staticDirectory: 'static',
      // 用项目自带 src/index.html 作 HTML 模板；不写这条 Taro 4 不会自动生成 dist/index.html
      htmlPluginOption: {
        template: 'src/index.html',
      },
      output: {
        filename: 'js/[name].[hash:8].js',
        chunkFilename: 'js/[name].[chunkhash:8].js',
      },
      miniCssExtractPluginOption: {
        ignoreOrder: true,
        filename: 'css/[name].[hash].css',
        chunkFilename: 'css/[name].[chunkhash].css',
      },
      postcss: {
        autoprefixer: {
          enable: true,
          config: {},
        },
        cssModules: {
          enable: true,
          config: {
            namingPattern: 'module',
            generateScopedName: '[name]__[local]___[hash:base64:5]',
          },
        },
      },
    },
    rn: {
      appName: 'safetyScout',
      postcss: {
        cssModules: {
          enable: false,
        },
      },
    },
  };

  if (process.env.NODE_ENV === 'development') {
    return merge({}, baseConfig, devConfig);
  }
  return merge({}, baseConfig, prodConfig);
});
