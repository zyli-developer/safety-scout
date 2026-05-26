/**
 * 单元测试：DesktopReport 页面.
 *
 * 验收要点：
 * - 加载中 → 渲染 ProgressIndicator
 * - 失败 → ErrorView 等价文案
 * - 成功 → 渲染 ReportSidebar + HazardCard 列表
 *
 * 备注：usePolling 没有 mount 时立即 fetch，第一次 tick 发生在 intervalMs 之后，
 * 因此测试里把 `pi`（poll_interval_ms）压到 20ms，确保 default 1s 的 waitFor 之
 * 内就能拿到 mockedGet 的返回值。
 */
import { render, screen, waitFor } from '@testing-library/react';
import Taro from '@tarojs/taro';

import DesktopReport from '../../src/pages/report/desktop';
import type { GetInspectionResponse } from '../../src/types/inspection';
import type { ReportPayload } from '../../src/types/report';

jest.mock('../../src/api/inspections', () => ({
  getInspection: jest.fn(),
}));
import { getInspection } from '../../src/api/inspections';

const mockedGet = getInspection as unknown as jest.Mock;
const mockedRouter = Taro.useRouter as unknown as jest.Mock;

const SAMPLE_REPORT: ReportPayload = {
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
      regulation: '《建筑施工高处作业安全技术规范》JGJ80-2016 第 5.1.2 条',
      suggestion: '改用合规直梯或脚手架',
    },
    {
      category_code: 'H2',
      category_name: '物体打击',
      description: '外架与结构间无防护',
      severity: 'medium',
      regulation: 'JGJ130-2011 第 6.2.1 条',
      suggestion: '加挂密目网',
    },
  ],
  model_meta: { provider: 'claude_cli', model: 'sonnet', latency_ms: 30000 },
};

describe('DesktopReport', () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedRouter.mockReturnValue({ params: { id: 'r-1', pi: '20', to: '60000' } });
  });

  it('renders ProgressTracker while processing', async () => {
    const resp: GetInspectionResponse = {
      inspection_id: 'r-1',
      status: 'processing',
      created_at: '2026-05-21T10:00:00Z',
      updated_at: '2026-05-21T10:00:01Z',
      report: null,
      error: null,
    };
    mockedGet.mockResolvedValue(resp);
    render(<DesktopReport />);
    await waitFor(() => {
      // ProgressTracker 渲染 3 节点：'拍照已就绪' / 'AI 分析中' / '报告就绪'。
      // 取 active 节点 'AI 分析中' 作为 processing 状态信号。
      expect(screen.getByText('AI 分析中')).toBeInTheDocument();
    });
  });

  it('renders sidebar + hazard list when succeeded', async () => {
    const resp: GetInspectionResponse = {
      inspection_id: 'r-1',
      status: 'succeeded',
      created_at: '2026-05-21T10:00:00Z',
      updated_at: '2026-05-21T10:00:30Z',
      report: SAMPLE_REPORT,
      error: null,
    };
    mockedGet.mockResolvedValue(resp);
    render(<DesktopReport />);

    await waitFor(() => {
      expect(screen.getByText('现场巡检报告')).toBeInTheDocument();
    });
    // 2026-05-24 B5: hazardCount=2 在 sidebar barNum + barLegend 都出现，
    // getByText('2') 会多匹配。改用 getAllByText 检查至少 1 处。
    expect(screen.getAllByText('2').length).toBeGreaterThan(0); // hazardCount
    expect(screen.getByText(/高处坠落/)).toBeInTheDocument();
    expect(screen.getByText(/物体打击/)).toBeInTheDocument();
  });

  it('renders timeout DesktopErrorView when polling exceeds timeout', async () => {
    // 永远返回 processing —— usePolling 永远不会满足 stopWhen，触发 isTimedOut。
    // to=50ms 让 elapsedMs 在两次 tick 内就超过；不依赖任何 wall-clock 精度。
    mockedRouter.mockReturnValue({ params: { id: 'r-1', pi: '20', to: '50' } });
    const resp: GetInspectionResponse = {
      inspection_id: 'r-1',
      status: 'processing',
      created_at: '2026-05-21T10:00:00Z',
      updated_at: '2026-05-21T10:00:01Z',
      report: null,
      error: null,
    };
    mockedGet.mockResolvedValue(resp);
    render(<DesktopReport />);
    await waitFor(() => {
      // DesktopErrorView 的硬编码 timeout 文案 —— 唯一不经 mapApiError 的 user-facing 字串
      expect(screen.getByText('AI 分析超时，请重试')).toBeInTheDocument();
    });
  });

  it('renders ErrorView on failed status', async () => {
    const resp: GetInspectionResponse = {
      inspection_id: 'r-1',
      status: 'failed',
      created_at: '2026-05-21T10:00:00Z',
      updated_at: '2026-05-21T10:00:30Z',
      report: null,
      error: {
        code: 'LLM_TIMEOUT',
        message: 'timed out',
        user_message: 'AI 分析超时，请稍后重试',
      },
    };
    mockedGet.mockResolvedValue(resp);
    render(<DesktopReport />);
    await waitFor(() => {
      expect(screen.getByText(/AI 分析超时|请稍后重试/)).toBeInTheDocument();
    });
  });
});
