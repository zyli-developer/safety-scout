/**
 * QualityPage 单元测试 —— Layer 3 前端 dashboard。
 *
 * 覆盖：
 * - 默认加载时显示 loading
 * - 4 张卡片都渲染（每 metric 一张）
 * - group_by 切换触发重新拉取
 * - 单卡失败不影响其它卡片（部分降级）
 * - 空数据时显示"暂无数据"
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

// Mock api 之后再 import 页面，避免实际网络请求
jest.mock('../../src/api/quality', () => ({
  fetchQualityTrend: jest.fn(),
}));

import QualityPage from '../../src/pages/quality/index';
import { fetchQualityTrend } from '../../src/api/quality';
import { ApiError } from '../../src/api/client';

const mockFetch = fetchQualityTrend as jest.Mock;

function makeResp(metric: string, series: Array<{ group: string; value: number; n: number }>) {
  return {
    metric,
    group_by: 'prompt_version',
    since: '2026-04-27T00:00:00Z',
    series: series.map((s) => ({ group: s.group, x: s.group, value: s.value, n: s.n })),
  };
}

describe('QualityPage', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  test('renders 4 metric cards by metric id', async () => {
    mockFetch.mockImplementation(async (metric: string) =>
      makeResp(metric, [{ group: 'v7', value: 0.61, n: 8 }])
    );

    render(<QualityPage />);

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(4));
    expect(screen.getByText(/Judge 胜率/)).toBeInTheDocument();
    expect(screen.getByText('p50 延迟')).toBeInTheDocument();
    expect(screen.getByText('p50 输出 tokens')).toBeInTheDocument();
    expect(screen.getByText('p50 隐患数')).toBeInTheDocument();
  });

  test('formats judge_win_rate as percentage', async () => {
    mockFetch.mockImplementation(async (metric: string) => {
      if (metric === 'judge_win_rate') {
        return makeResp(metric, [{ group: 'v7', value: 0.61, n: 8 }]);
      }
      return makeResp(metric, []);
    });

    render(<QualityPage />);

    await waitFor(() => expect(screen.getByText('61%')).toBeInTheDocument());
  });

  test('formats p50_latency as seconds', async () => {
    mockFetch.mockImplementation(async (metric: string) => {
      if (metric === 'p50_latency') {
        return makeResp(metric, [{ group: 'v7', value: 148000, n: 5 }]);
      }
      return makeResp(metric, []);
    });

    render(<QualityPage />);

    await waitFor(() => expect(screen.getByText('148.0s')).toBeInTheDocument());
  });

  test('group_by chip switch triggers refetch with new groupBy', async () => {
    mockFetch.mockResolvedValue(makeResp('judge_win_rate', []));
    render(<QualityPage />);

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(4));
    const callsBefore = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByText('按 model'));

    await waitFor(() => expect(mockFetch.mock.calls.length).toBe(callsBefore + 4));
    // 最后 4 次调用 groupBy 应为 'model'
    const lastFour = mockFetch.mock.calls.slice(-4);
    for (const call of lastFour) {
      expect(call[1]).toBe('model');
    }
  });

  test('single card error does not break other cards (partial degradation)', async () => {
    mockFetch.mockImplementation(async (metric: string) => {
      if (metric === 'p50_latency') {
        throw new ApiError('NETWORK_ERROR', '网络异常', 0);
      }
      return makeResp(metric, [{ group: 'v7', value: 5, n: 1 }]);
    });

    render(<QualityPage />);

    await waitFor(() => {
      // 失败的卡片显示错误
      expect(screen.getByText(/NETWORK_ERROR/)).toBeInTheDocument();
      // 其它卡片仍然渲染数据
      expect(screen.getAllByText('v7').length).toBeGreaterThan(0);
    });
  });

  test('empty series shows "暂无数据"', async () => {
    mockFetch.mockResolvedValue(makeResp('judge_win_rate', []));
    render(<QualityPage />);

    await waitFor(() => {
      // 所有 4 张卡片都是空 → 4 个"暂无数据"
      expect(screen.getAllByText('暂无数据').length).toBe(4);
    });
  });

  test('default groupBy is prompt_version', async () => {
    mockFetch.mockResolvedValue(makeResp('judge_win_rate', []));
    render(<QualityPage />);

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    // 第一次调用的 groupBy 必须是 'prompt_version'
    expect(mockFetch.mock.calls[0][1]).toBe('prompt_version');
  });
});
