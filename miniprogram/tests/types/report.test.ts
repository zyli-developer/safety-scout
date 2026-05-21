/** spec 一致性测试：docs/specs/report-schema.md 的第一个 ```json 块必须能被
 *  当作 ReportPayload 解析。schema 漂移时这个测试会挂。
 */
import { readFileSync } from 'fs';
import { join } from 'path';
import type { ReportPayload } from '../../src/types/report';

const SPEC_PATH = join(__dirname, '../../../docs/specs/report-schema.md');

function extractFirstJsonBlock(md: string): unknown {
  const match = md.match(/```json\s*\n([\s\S]*?)\n```/);
  if (!match) throw new Error('找不到 ```json 块');
  return JSON.parse(match[1]);
}

describe('ReportPayload 类型 vs report-schema.md', () => {
  it('spec 示例 JSON 应当符合 ReportPayload 形态', () => {
    const md = readFileSync(SPEC_PATH, 'utf-8');
    const example = extractFirstJsonBlock(md) as ReportPayload;

    expect(typeof example.inspection_id).toBe('string');
    expect(typeof example.created_at).toBe('string');
    expect(typeof example.plain_warning).toBe('string');
    expect(typeof example.summary).toBe('string');
    expect(['high', 'medium', 'low']).toContain(example.overall_severity);
    expect(Array.isArray(example.hazards)).toBe(true);
    example.hazards.forEach((h) => {
      expect(/^H([1-9]|10)$/.test(h.category_code)).toBe(true);
      expect(['high', 'medium', 'low']).toContain(h.severity);
      expect(typeof h.description).toBe('string');
      expect(typeof h.suggestion).toBe('string');
    });
    expect(['claude_cli', 'doubao', 'fake']).toContain(example.model_meta.provider);
    expect(typeof example.model_meta.model).toBe('string');
    expect(typeof example.model_meta.latency_ms).toBe('number');
  });
});
