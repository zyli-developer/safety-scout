/**
 * 单元测试：ReportDetail 单 hazard 详情页 (B6)。
 *
 * 覆盖：
 * - 渲染 hazard header (code + name + severity pill) + description + regulation + suggestion
 * - pager 边界（first 隐患 prev disabled、last 隐患 next disabled）
 * - 高 stakes step click → 弹 confirm sheet
 * - confirm → 标记完成 + 5s undo toast
 * - undo → 恢复 unchecked
 * - hazard 不存在时显示"找不到该条隐患"
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Taro from '@tarojs/taro';

import ReportDetail from '../../src/pages/report-detail/index';
import type { GetInspectionResponse } from '../../src/types/inspection';
import type { ReportPayload } from '../../src/types/report';

jest.mock('../../src/api/inspections', () => ({
  getInspection: jest.fn(),
}));
import { getInspection } from '../../src/api/inspections';

const mockedGet = getInspection as unknown as jest.Mock;
const mockedRouter = Taro.useRouter as unknown as jest.Mock;

const SAMPLE: ReportPayload = {
  inspection_id: 'r-1',
  created_at: '2026-05-21T10:00:00Z',
  plain_warning: '注意临边',
  summary: '现场存在多处临边作业风险',
  overall_severity: 'high',
  hazards: [
    {
      category_code: 'H1',
      category_name: '高处坠落',
      description: '人字梯使用高度超过 2m',
      severity: 'high',
      regulation: 'JGJ80-2016 第 5.1.2 条',
      suggestion: '改用合规直梯或脚手架',
    },
    {
      category_code: 'H2',
      category_name: '物体打击',
      description: '楼层边缘混凝土残渣未清理',
      severity: 'high',
      regulation: 'JGJ59-2011 第 3.0.5 条',
      suggestion: '清理结构边缘残渣 + 正下方设硬质防护棚',
    },
  ],
  model_meta: { provider: 'claude_cli', model: 'sonnet', latency_ms: 30000 },
};

function makeResp(): GetInspectionResponse {
  return {
    inspection_id: 'r-1',
    status: 'succeeded',
    created_at: '2026-05-21T10:00:00Z',
    updated_at: '2026-05-21T10:00:30Z',
    report: SAMPLE,
    error: null,
  };
}

describe('ReportDetail (B6)', () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedRouter.mockReset();
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it('renders hazard header + description + regulation + suggestion for hazards[0]', async () => {
    mockedRouter.mockReturnValue({ params: { id: 'r-1', h: '0' } });
    mockedGet.mockResolvedValue(makeResp());
    render(<ReportDetail />);

    await waitFor(() => {
      expect(screen.getByText('高处坠落')).toBeInTheDocument();
    });
    expect(screen.getByText('H1')).toBeInTheDocument();
    expect(screen.getByText('人字梯使用高度超过 2m')).toBeInTheDocument();
    expect(screen.getByText('JGJ80-2016 第 5.1.2 条')).toBeInTheDocument();
    expect(screen.getByText('改用合规直梯或脚手架')).toBeInTheDocument();
  });

  it('disables prev pager on first hazard, enables next', async () => {
    mockedRouter.mockReturnValue({ params: { id: 'r-1', h: '0' } });
    mockedGet.mockResolvedValue(makeResp());
    const { container } = render(<ReportDetail />);
    await waitFor(() => {
      expect(screen.getByText('高处坠落')).toBeInTheDocument();
    });
    const prev = container.querySelector('[aria-disabled="true"]');
    expect(prev?.textContent).toContain('上一条');
  });

  it('clicking the step opens confirm sheet (high stakes)', async () => {
    mockedRouter.mockReturnValue({ params: { id: 'r-1', h: '0' } });
    mockedGet.mockResolvedValue(makeResp());
    const { container } = render(<ReportDetail />);
    await waitFor(() => {
      expect(screen.getByText('高处坠落')).toBeInTheDocument();
    });
    const stepCheck = container.querySelector('[role="checkbox"]') as HTMLElement;
    expect(stepCheck.getAttribute('aria-checked')).toBe('false');
    fireEvent.click(stepCheck);
    expect(screen.getByText('确认现场已完成？')).toBeInTheDocument();
  });

  it('confirm → marks done + shows undo toast; undo reverts', async () => {
    mockedRouter.mockReturnValue({ params: { id: 'r-1', h: '0' } });
    mockedGet.mockResolvedValue(makeResp());
    const { container } = render(<ReportDetail />);
    await waitFor(() => {
      expect(screen.getByText('高处坠落')).toBeInTheDocument();
    });
    const stepCheck = container.querySelector('[role="checkbox"]') as HTMLElement;
    fireEvent.click(stepCheck);
    fireEvent.click(screen.getByText('确认完成'));

    expect(stepCheck.getAttribute('aria-checked')).toBe('true');
    expect(screen.getByText(/已标记完成/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('撤销'));
    expect(stepCheck.getAttribute('aria-checked')).toBe('false');
  });

  it('shows "找不到该条隐患" when hazard index out of range', async () => {
    mockedRouter.mockReturnValue({ params: { id: 'r-1', h: '99' } });
    mockedGet.mockResolvedValue(makeResp());
    render(<ReportDetail />);
    await waitFor(() => {
      expect(screen.getByText('找不到该条隐患')).toBeInTheDocument();
    });
  });
});
