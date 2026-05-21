/**
 * 单元测试：DesktopIndex 页面.
 *
 * 验收要点：
 * - 渲染上传区（UploadDropzone）+ 拍摄要点 + AI 引擎元信息
 * - 上传文件后调 createInspection 并 Taro.navigateTo 跳报告页
 * - 上传失败时 Taro.showToast 展示 user_message
 *
 * createInspection 用 jest.mock 替换，避免真的发请求。
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Taro from '@tarojs/taro';

jest.mock('../../src/api/inspections', () => ({
  createInspection: jest.fn(),
}));

import DesktopIndex from '../../src/pages/index/desktop';
import { createInspection } from '../../src/api/inspections';
import { ApiError } from '../../src/api/client';

const mockedCreate = createInspection as unknown as jest.Mock;
const mockedNavigate = Taro.navigateTo as unknown as jest.Mock;
const mockedToast = Taro.showToast as unknown as jest.Mock;

function makeFile(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff])], 'photo.jpg', { type: 'image/jpeg' });
}

describe('DesktopIndex', () => {
  beforeEach(() => {
    mockedCreate.mockReset();
    mockedNavigate.mockReset();
    mockedToast.mockReset();
  });

  it('renders dropzone + 拍摄要点 list + AI 引擎 footer', () => {
    render(<DesktopIndex />);
    expect(screen.getByText('工地隐患识别')).toBeInTheDocument();
    expect(screen.getByText(/AI · SITE HAZARD INSPECTION/)).toBeInTheDocument();
    expect(screen.getByText(/拍摄要点/)).toBeInTheDocument();
    expect(screen.getByText(/贴近隐患位置/)).toBeInTheDocument();
    expect(screen.getByText(/AI ENGINE/)).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'false');
  });

  it('navigates to report on successful upload', async () => {
    mockedCreate.mockResolvedValueOnce({
      inspection_id: 'desk-1',
      poll_url: '/api/v1/inspections/desk-1',
      poll_interval_ms: 2000,
      timeout_ms: 330_000,
      status: 'queued',
    });
    const { container } = render(<DesktopIndex />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledTimes(1));
    expect(mockedCreate).toHaveBeenCalledWith(expect.any(File));
    await waitFor(() => expect(mockedNavigate).toHaveBeenCalledTimes(1));
    const navArg = mockedNavigate.mock.calls[0][0];
    expect(navArg.url).toMatch(/^\/pages\/report\/index\?id=desk-1/);
  });

  it('shows toast on upload error', async () => {
    // 用真的 ApiError 实例，因为 mapApiError 依赖 instanceof ApiError 才走 userMessage
    const err = new ApiError('INVALID_IMAGE', '图片格式不支持', 400);
    mockedCreate.mockRejectedValueOnce(err);
    const { container } = render(<DesktopIndex />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });

    await waitFor(() => expect(mockedToast).toHaveBeenCalledTimes(1));
    const arg = mockedToast.mock.calls[0][0];
    expect(arg.title).toContain('图片格式不支持');
  });
});
