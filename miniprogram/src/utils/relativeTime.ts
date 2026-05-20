/**
 * 中文相对时间格式化器。
 *
 * 用于报告页 HeroBanner 的 meta 行，例如 "中风险 · 2 分钟前"。
 *
 * 入参：
 *   iso —— 后端返回的 ISO 时间字符串（report.created_at 同一格式）
 *   now —— 注入用于测试；默认 new Date()
 *
 * 规则（5 档）：
 *   < 60s          → "刚刚"
 *   < 60min        → "N 分钟前"
 *   同一日历日      → "今天 HH:mm"
 *   前一日历日      → "昨天 HH:mm"
 *   更早            → "YYYY-MM-DD HH:mm"
 *
 * "同一日历日" 按本地时区比对（用户在工地是中国本地时间）。
 */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (isNaN(then.getTime())) return iso;

  const diffMs = now.getTime() - then.getTime();
  const diffMin = Math.floor(diffMs / 60_000);

  if (diffMs < 60_000) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;

  const sameDay =
    now.getFullYear() === then.getFullYear() &&
    now.getMonth() === then.getMonth() &&
    now.getDate() === then.getDate();
  const hh = String(then.getHours()).padStart(2, '0');
  const mm = String(then.getMinutes()).padStart(2, '0');

  if (sameDay) return `今天 ${hh}:${mm}`;

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday =
    yesterday.getFullYear() === then.getFullYear() &&
    yesterday.getMonth() === then.getMonth() &&
    yesterday.getDate() === then.getDate();
  if (isYesterday) return `昨天 ${hh}:${mm}`;

  const yyyy = then.getFullYear();
  const mo = String(then.getMonth() + 1).padStart(2, '0');
  const dd = String(then.getDate()).padStart(2, '0');
  return `${yyyy}-${mo}-${dd} ${hh}:${mm}`;
}
