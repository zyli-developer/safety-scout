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
      patterns: [
        // H5: 把 src/assets/fonts 拷到 dist/assets/fonts 让 @font-face 找得到。
        // weapp 上拷过去也无害，weapp build 自己会忽略未被引用的资源。
        { from: 'src/assets/fonts/', to: 'dist/assets/fonts/', ignore: ['*.md'] },
      ],
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
        // H5 关掉 pxtransform：clean-minimal 桌面 H5 需要 viewport-相关的 clamp()
        // 直接生效。Taro 默认把 px → rem，但 H5 没设 html font-size，rem 接 16px →
        // 字号被压扁；clamp(40px, 3.6vw, 56px) 一旦被转 rem，vw 计算也走样。
        // 关掉后 px 留原值，clamp / @media 都按真实 viewport 行事。
        // weapp 端的 pxtransform 仍由 mini.postcss 保留（按 designWidth 750 缩放）。
        pxtransform: {
          enable: false,
        },
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
