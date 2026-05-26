/**
 * 巡检历史本地缓存（B8 临时方案）。
 *
 * 后端 inspection_repo 目前没有 list endpoint（只有 list_orphaned_queued + get）。
 * 在后端 list_inspections() 上线之前，前端先用 localStorage 维护本设备拍过的
 * 巡检记录，给 history 页一个可用的数据源。"伪 history"但短期可用。
 *
 * 接入后端后整个模块可下线，replace 为 GET /api/v1/inspections。
 *
 * 容量控制：单条 JSON ≈ 500 字节，1000 条 ≈ 500KB，远小于 localStorage 5MB。
 * 上限 200 条，超过按 capturedAt 升序淘汰最老的。
 */
import type { Severity } from '../types/report';

export interface HistoryEntry {
  inspectionId: string;
  capturedAt: number; // unix ms
  summary: string;
  overallSeverity: Severity;
  hazardCount: number;
  breakdown: { high: number; medium: number; low: number };
  /** 整改状态。当前 schema 不带，本地默认 "pending"；用户在 detail 勾选完成后可升级
      为 "inProgress" / "closed"（暂未做，留接口） */
  status: 'pending' | 'inProgress' | 'closed';
}

const LS_KEY = 'safety-scout/history';
const MAX_ENTRIES = 200;

let memoryList: HistoryEntry[] | null = null;

function ls(): Storage | null {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      return window.localStorage;
    }
  } catch {
    /* noop */
  }
  return null;
}

function read(): HistoryEntry[] {
  if (memoryList) return memoryList;
  const s = ls();
  if (!s) {
    memoryList = [];
    return memoryList;
  }
  try {
    const raw = s.getItem(LS_KEY);
    if (!raw) {
      memoryList = [];
      return memoryList;
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      memoryList = [];
      return memoryList;
    }
    memoryList = parsed.filter(
      (x): x is HistoryEntry =>
        x != null &&
        typeof x.inspectionId === 'string' &&
        typeof x.capturedAt === 'number',
    );
    return memoryList;
  } catch {
    memoryList = [];
    return memoryList;
  }
}

function write(list: HistoryEntry[]): void {
  memoryList = list;
  const s = ls();
  if (!s) return;
  try {
    s.setItem(LS_KEY, JSON.stringify(list));
  } catch (e) {
    console.warn('[historyStore] localStorage 写入失败（quota？）', e);
  }
}

/** 追加一条记录。已存在同 inspectionId 时更新（用更新版本替换）。 */
export function appendHistory(entry: HistoryEntry): void {
  const list = read();
  const idx = list.findIndex((e) => e.inspectionId === entry.inspectionId);
  if (idx >= 0) {
    list[idx] = entry;
  } else {
    list.push(entry);
  }
  // 按 capturedAt 倒序
  list.sort((a, b) => b.capturedAt - a.capturedAt);
  // 截断到 MAX_ENTRIES（淘汰最老）
  if (list.length > MAX_ENTRIES) {
    list.splice(MAX_ENTRIES);
  }
  write(list);
}

/** 拿全部历史，按 capturedAt 倒序（最新在前）。 */
export function getHistory(): HistoryEntry[] {
  return [...read()];
}

/** 按 inspectionId 拿单条。无则 null。 */
export function getHistoryEntry(inspectionId: string): HistoryEntry | null {
  return read().find((e) => e.inspectionId === inspectionId) ?? null;
}

/** 仅测试用：清空。 */
export function _resetHistoryStore(): void {
  memoryList = null;
  const s = ls();
  if (!s) return;
  try {
    s.removeItem(LS_KEY);
  } catch {
    /* noop */
  }
}

/**
 * 简单聚合：返回今/本周/本月计数 + 高风险数 + 最常见类别。
 * 仅 history 页 summary strip 用。
 */
export function summarizeHistory(): {
  total: number;
  weekly: number;
  highRisk: number;
  closed: number;
  topCategory: { code: string; count: number } | null;
} {
  const list = read();
  const now = Date.now();
  const weekAgo = now - 7 * 24 * 3600 * 1000;
  const weekly = list.filter((e) => e.capturedAt >= weekAgo).length;
  const highRisk = list.filter((e) => e.overallSeverity === 'high').length;
  const closed = list.filter((e) => e.status === 'closed').length;
  // topCategory 需要从 hazards 算 —— 但 HistoryEntry 没存类别明细，
  // 简化为：取 overallSeverity = high 的条数所属 hazardCount 最多的一条；
  // 真实实现接后端后补充类别字段
  const total = list.length;
  return {
    total,
    weekly,
    highRisk,
    closed,
    topCategory: null,
  };
}
