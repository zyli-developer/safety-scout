declare function defineAppConfig<T>(config: T): T;

export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/report/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#fff',
    navigationBarTitleText: 'Safety Scout',
    navigationBarTextStyle: 'black',
  },
});
