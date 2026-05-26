/**
 * historyStore 单元测试（B8）。
 */
import {
  appendHistory,
  getHistory,
  getHistoryEntry,
  summarizeHistory,
  _resetHistoryStore,
  type HistoryEntry,
} from '../../src/utils/historyStore';

function makeEntry(overrides: Partial<HistoryEntry> = {}): HistoryEntry {
  return {
    inspectionId: 'i-' + Math.random().toString(36).slice(2, 9),
    capturedAt: Date.now(),
    summary: '现场存在多处隐患',
    overallSeverity: 'high',
    hazardCount: 3,
    breakdown: { high: 3, medium: 0, low: 0 },
    status: 'pending',
    ...overrides,
  };
}

describe('historyStore', () => {
  beforeEach(() => {
    _resetHistoryStore();
  });

  it('returns empty list on cold start', () => {
    expect(getHistory()).toEqual([]);
  });

  it('appends entries and returns them sorted by capturedAt desc', () => {
    const older = makeEntry({ inspectionId: 'a', capturedAt: 1000 });
    const newer = makeEntry({ inspectionId: 'b', capturedAt: 2000 });
    appendHistory(older);
    appendHistory(newer);
    const list = getHistory();
    expect(list.map((e) => e.inspectionId)).toEqual(['b', 'a']);
  });

  it('updates existing entry with same inspectionId instead of duplicating', () => {
    const e1 = makeEntry({ inspectionId: 'x', hazardCount: 3 });
    appendHistory(e1);
    appendHistory({ ...e1, hazardCount: 5 });
    const list = getHistory();
    expect(list.length).toBe(1);
    expect(list[0].hazardCount).toBe(5);
  });

  it('getHistoryEntry returns null for missing id', () => {
    appendHistory(makeEntry({ inspectionId: 'x' }));
    expect(getHistoryEntry('y')).toBeNull();
    expect(getHistoryEntry('x')?.inspectionId).toBe('x');
  });

  it('schemaVersion round-trips through localStorage', () => {
    appendHistory(makeEntry({ inspectionId: 'v2-id', schemaVersion: 'v2' }));
    appendHistory(makeEntry({ inspectionId: 'v1-id', schemaVersion: 'v1' }));
    appendHistory(makeEntry({ inspectionId: 'legacy-id' })); // 不带 schemaVersion 字段
    expect(getHistoryEntry('v2-id')?.schemaVersion).toBe('v2');
    expect(getHistoryEntry('v1-id')?.schemaVersion).toBe('v1');
    expect(getHistoryEntry('legacy-id')?.schemaVersion).toBeUndefined();
  });

  it('schemaVersion 兼容老 localStorage：从 raw JSON parse 出来的老条目不报错', () => {
    // 模拟旧版本写入的、不带 schemaVersion 的本地存储
    const raw = JSON.stringify([
      {
        inspectionId: 'old-1',
        capturedAt: Date.now(),
        summary: '老报告',
        overallSeverity: 'low',
        hazardCount: 1,
        breakdown: { high: 0, medium: 0, low: 1 },
        status: 'pending',
      },
    ]);
    // 写 raw 到 localStorage，清掉 memory cache 强制走 read() parse 路径
    window.localStorage.setItem('safety-scout/history', raw);
    _resetHistoryStore();
    window.localStorage.setItem('safety-scout/history', raw);
    const e = getHistoryEntry('old-1');
    expect(e).not.toBeNull();
    expect(e?.schemaVersion).toBeUndefined();
  });

  it('summarizeHistory computes total / weekly / highRisk / closed', () => {
    const now = Date.now();
    appendHistory(makeEntry({ inspectionId: 'a', capturedAt: now, overallSeverity: 'high' }));
    appendHistory(makeEntry({ inspectionId: 'b', capturedAt: now - 1, overallSeverity: 'medium' }));
    appendHistory(
      makeEntry({
        inspectionId: 'c',
        capturedAt: now - 14 * 24 * 3600 * 1000,
        overallSeverity: 'low',
        status: 'closed',
      }),
    );
    const s = summarizeHistory();
    expect(s.total).toBe(3);
    expect(s.weekly).toBe(2); // a + b 在 7 天内；c 14 天前
    expect(s.highRisk).toBe(1);
    expect(s.closed).toBe(1);
  });
});
