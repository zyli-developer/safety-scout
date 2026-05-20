/**
 * relativeTime(iso, now?) —— 报告 banner 用的中文相对时间。
 *
 * 规则：
 * - < 60s   → "刚刚"
 * - < 60min → "N 分钟前"
 * - 同一日历日 → "今天 HH:mm"
 * - 前一日历日 → "昨天 HH:mm"
 * - 更早 → "YYYY-MM-DD HH:mm"
 *
 * 测试通过注入 now 保证确定性。
 */
import { relativeTime } from '../../src/utils/relativeTime';

const NOW = new Date('2026-05-20T14:32:00');

describe('relativeTime', () => {
  it('"刚刚" when within 60 seconds', () => {
    const iso = new Date(NOW.getTime() - 30_000).toISOString();
    expect(relativeTime(iso, NOW)).toBe('刚刚');
  });

  it('"N 分钟前" within the hour', () => {
    const iso = new Date(NOW.getTime() - 5 * 60_000).toISOString();
    expect(relativeTime(iso, NOW)).toBe('5 分钟前');
  });

  it('"今天 HH:mm" for same calendar day, hours earlier', () => {
    const iso = new Date(NOW.getTime() - 3 * 60 * 60_000).toISOString();
    expect(relativeTime(iso, NOW)).toBe('今天 11:32');
  });

  it('"昨天 HH:mm" for previous calendar day', () => {
    const iso = new Date('2026-05-19T22:10:00').toISOString();
    expect(relativeTime(iso, NOW)).toBe('昨天 22:10');
  });

  it('"YYYY-MM-DD HH:mm" for older dates', () => {
    const iso = new Date('2026-05-15T09:00:00').toISOString();
    expect(relativeTime(iso, NOW)).toBe('2026-05-15 09:00');
  });
});
