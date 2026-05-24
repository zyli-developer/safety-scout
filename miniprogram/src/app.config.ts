declare function defineAppConfig<T>(config: T): T;

export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/report/index',
    // 2026-05-24 B6：单 hazard 详情页（从 report 列表"查看条款 →"跳过来）
    'pages/report-detail/index',
    // 2026-05-24 B8：巡检历史列表（localStorage 数据源，后端 list endpoint 上线前的临时方案）
    'pages/history/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#fff',
    navigationBarTitleText: 'Safety Scout',
    navigationBarTextStyle: 'black',
  },
});
