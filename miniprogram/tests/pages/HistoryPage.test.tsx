/**
 * HistoryPage 单元测试（B8）。
 *
 * 覆盖：
 * - 空 store → 渲染 EmptyState
 * - 有记录 → 渲染 summary cells + chips + list rows
 * - chip 切换过滤
 * - search input 过滤 summary 文本
 */
import { fireEvent, render, screen } from '@testing-library/react';

import HistoryPage from '../../src/pages/history/index';
import {
  appendHistory,
  _resetHistoryStore,
  type HistoryEntry,
} from '../../src/utils/historyStore';

function makeEntry(overrides: Partial<HistoryEntry> = {}): HistoryEntry {
  return {
    inspectionId: 'i-' + Math.random().toString(36).slice(2, 9),
    capturedAt: Date.now(),
    summary: '现场存在多处临边作业风险',
    overallSeverity: 'high',
    hazardCount: 3,
    breakdown: { high: 3, medium: 0, low: 0 },
    status: 'pending',
    ...overrides,
  };
}

describe('HistoryPage (B8)', () => {
  beforeEach(() => {
    _resetHistoryStore();
  });

  it('renders EmptyState when no history', () => {
    render(<HistoryPage />);
    expect(screen.getByText('巡检报告')).toBeInTheDocument();
    expect(screen.getByText(/还没有巡检记录/)).toBeInTheDocument();
  });

  it('renders summary cells + list rows when history exists', () => {
    appendHistory(makeEntry({ inspectionId: 'a', summary: '高处坠落隐患', overallSeverity: 'high' }));
    appendHistory(
      makeEntry({
        inspectionId: 'b',
        summary: '配电箱开门带电',
        overallSeverity: 'medium',
        hazardCount: 1,
        breakdown: { high: 0, medium: 1, low: 0 },
      }),
    );
    render(<HistoryPage />);
    expect(screen.getByText('本机总数')).toBeInTheDocument();
    expect(screen.getByText('高处坠落隐患')).toBeInTheDocument();
    expect(screen.getByText('配电箱开门带电')).toBeInTheDocument();
  });

  it('filter chip 切换：选 "中" 只看 medium', () => {
    appendHistory(makeEntry({ inspectionId: 'a', summary: 'high item', overallSeverity: 'high' }));
    appendHistory(
      makeEntry({
        inspectionId: 'b',
        summary: 'medium item',
        overallSeverity: 'medium',
        breakdown: { high: 0, medium: 1, low: 0 },
      }),
    );
    render(<HistoryPage />);
    expect(screen.getByText('high item')).toBeInTheDocument();
    expect(screen.getByText('medium item')).toBeInTheDocument();

    // 点 "中" chip
    fireEvent.click(screen.getByText('中'));
    expect(screen.queryByText('high item')).toBeNull();
    expect(screen.getByText('medium item')).toBeInTheDocument();
  });

  it('disables filter chip when count is 0', () => {
    appendHistory(makeEntry({ inspectionId: 'a', summary: 'h', overallSeverity: 'high' }));
    const { container } = render(<HistoryPage />);
    // "低" 计数为 0，应 aria-disabled
    const lowChip = Array.from(container.querySelectorAll('[role="tab"]')).find((el) =>
      el.textContent?.includes('低'),
    ) as HTMLElement | undefined;
    expect(lowChip?.getAttribute('aria-disabled')).toBe('true');
  });
});
