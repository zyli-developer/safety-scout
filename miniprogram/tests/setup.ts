// Jest setup: globally mock @tarojs/taro since jsdom can't actually run wx.*
import '@testing-library/jest-dom';

jest.mock('@tarojs/taro', () => ({
  __esModule: true,
  default: {
    request: jest.fn(),
    uploadFile: jest.fn(),
    chooseMedia: jest.fn(),
    navigateTo: jest.fn(),
    showToast: jest.fn(),
    useRouter: jest.fn(() => ({ params: {} })),
  },
}));
