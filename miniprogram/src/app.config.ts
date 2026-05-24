declare function defineAppConfig<T>(config: T): T;

export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/report/index',
    // 2026-05-24 B6：单 hazard 详情页（从 report 列表"查看条款 →"跳过来）
    'pages/report-detail/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#fff',
    navigationBarTitleText: 'Safety Scout',
    navigationBarTextStyle: 'black',
  },
});
