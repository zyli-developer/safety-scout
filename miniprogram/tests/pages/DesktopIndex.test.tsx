/**
 * 单元测试：DesktopIndex (clean-minimal)。
 *
 * 验收要点：
 * - 渲染 page header（eyebrow + h1 "开始一次现场巡检"）+ dropzone 卡（顶部标题
 *   "上传现场照片" + spec + dropzone + 底部模型可用性条）+ 右侧今日 + 最近巡检卡
 * - 上传文件后调 createInspection 并 Taro.navigateTo 跳报告页
 * - 上传失败时 Taro.showToast 展示 user_message
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

describe('DesktopIndex (clean-minimal)', () => {
  beforeEach(() => {
    mockedCreate.mockReset();
    mockedNavigate.mockReset();
    mockedToast.mockReset();
  });

  it('renders hero + dropzone card + 三步流程卡 + aside cards', () => {
    const { container } = render(<DesktopIndex />);
    // 2026-05-24：h1 改 "拍一张工地照片..."，删 eyebrow 与 engineStrip（模型名 dev-chrome）
    expect(screen.getByText(/拍一张工地照片/)).toBeInTheDocument();
    expect(screen.getByText('上传现场照片')).toBeInTheDocument();
    expect(screen.getByText(/拖拽图片到此处/)).toBeInTheDocument();
    // engineStrip "Claude Sonnet 4.5" 已删除，确保不再出现
    expect(screen.queryByText(/Claude Sonnet/)).toBeNull();
    // 三步流程卡的 step num 是新加的
    expect(screen.getByText(/01 · 拍照/)).toBeInTheDocument();
    expect(screen.getByText(/02 · 等待/)).toBeInTheDocument();
    expect(screen.getByText(/03 · 看报告/)).toBeInTheDocument();
    expect(screen.getByText('今日巡检')).toBeInTheDocument();
    expect(screen.getByText('最近巡检')).toBeInTheDocument();
    // dropzone 是页面里唯一带 aria-busy 的元素
    const dropzone = container.querySelector('[aria-busy]');
    expect(dropzone).toHaveAttribute('aria-busy', 'false');
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
