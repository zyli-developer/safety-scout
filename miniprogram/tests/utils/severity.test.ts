/** severity 工具的单测：排序权重 + 稳定排序 + 三档键完整。 */
import type { Hazard, Severity } from '../../src/types/report';
import {
  SEVERITY_COLOR,
  SEVERITY_LABEL,
  SEVERITY_ORDER,
  sortBySeverity,
} from '../../src/utils/severity';

function makeHazard(severity: Severity, description: string): Hazard {
  return {
    category_code: 'H1',
    category_name: '高处作业',
    description,
    severity,
    regulation: '',
    suggestion: '示例整改建议',
  };
}

describe('utils/severity', () => {
  it('sortBySeverity puts high before medium before low', () => {
    const input: Hazard[] = [
      makeHazard('low', 'L'),
      makeHazard('high', 'H'),
      makeHazard('medium', 'M'),
    ];

    const out = sortBySeverity(input);

    expect(out.map((h) => h.severity)).toEqual(['high', 'medium', 'low']);
  });

  it('sortBySeverity preserves stability for same severity', () => {
    const a = makeHazard('high', 'A');
    const b = makeHazard('high', 'B');
    const c = makeHazard('low', 'C');

    const out = sortBySeverity([a, b, c]);

    expect(out.map((h) => h.description)).toEqual(['A', 'B', 'C']);
  });

  it('SEVERITY_COLOR/LABEL/ORDER cover all three severities', () => {
    const keys: Severity[] = ['high', 'medium', 'low'];
    for (const k of keys) {
      expect(SEVERITY_ORDER[k]).toBeGreaterThan(0);
      expect(SEVERITY_COLOR[k]).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(SEVERITY_LABEL[k]).toMatch(/风险$/);
    }
    expect(Object.keys(SEVERITY_ORDER)).toHaveLength(3);
    expect(Object.keys(SEVERITY_COLOR)).toHaveLength(3);
    expect(Object.keys(SEVERITY_LABEL)).toHaveLength(3);
  });
});
