// Clean — desktop report screen.

function DesktopReport({ severity = 'high' }) {
  const hazards = SAMPLE_HAZARDS;
  const total = hazards.length;
  const counts = {
    high: hazards.filter(h => h.severity === 'high').length,
    medium: hazards.filter(h => h.severity === 'medium').length,
    low: hazards.filter(h => h.severity === 'low').length,
  };

  return (
    <div className="clean" style={{ minHeight: '100%', background: 'var(--bg)' }}>
      <TopNav activeTab="reports" />

      <div className="dt-shell-report">
        {/* Breadcrumb */}
        <div className="caption" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ cursor: 'pointer' }}>报告</span>
          <Icon name="chevronRight" size={12} color="var(--ink-3)" />
          <span style={{ color: 'var(--ink-2)' }} className="mono">NO.2026-05-21-3742</span>
        </div>

        {/* Page header */}
        <div className="dt-page-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <SeverityPill level={severity} solid />
              <span className="caption mono">NO.2026-05-21-3742</span>
            </div>
            <h1 className="title-lg" style={{ marginBottom: 0 }}>
              北区 5F 楼板巡检报告
            </h1>
            <p className="body" style={{ marginTop: 10, marginBottom: 0 }}>
              上海·浦东金桥项目 · 王立 · 2026-05-21 14:30 · 由 Claude Sonnet 4.5 分析
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary">
              <Icon name="download" size={16} /> 导出 PDF
            </button>
            <button className="btn btn-secondary">
              <Icon name="share" size={16} /> 分享
            </button>
            <button className="btn btn-primary">
              <Icon name="arrowUp" size={16} /> 转派班组
            </button>
          </div>
        </div>

        {/* Hero: photo + summary */}
        <div className="dt-grid-hero">
          <Photo src={PHOTO_URLS.scaff} ratio="4/3" overlay
                 meta="14:30:12 · 31.245°N 121.589°E · 23m" />

          <div className="card" style={{ padding: 28, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <span className="eyebrow">巡检概要</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 12 }}>
                <span className="title-xl" style={{ fontSize: 72, lineHeight: 0.95 }}>{total}</span>
                <span className="body muted">项隐患</span>
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <SeverityPill level="high" count={counts.high} />
                <SeverityPill level="medium" count={counts.medium} />
                <SeverityPill level="low" count={counts.low} />
              </div>

              <p className="body-sm" style={{ marginTop: 20, marginBottom: 0 }}>
                {SAMPLE_REPORT.summary}
              </p>
            </div>

            {/* Mini meta */}
            <div style={{
              marginTop: 24, paddingTop: 20,
              borderTop: '1px solid var(--line)',
              display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16,
            }}>
              <div>
                <span className="caption">分析耗时</span>
                <div className="mono" style={{ fontSize: 14, color: 'var(--ink)', marginTop: 2 }}>61.4 秒</div>
              </div>
              <div>
                <span className="caption">类别命中</span>
                <div className="mono" style={{ fontSize: 14, color: 'var(--ink)', marginTop: 2 }}>5 / 10</div>
              </div>
            </div>
          </div>
        </div>

        {/* Alarm */}
        <div style={{ marginBottom: 32 }}>
          <AlarmBox>{SAMPLE_REPORT.plain_warning}</AlarmBox>
        </div>

        {/* Hazard list */}
        <div className="card" style={{ padding: 0 }}>
          <div style={{
            padding: '20px 28px',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            borderBottom: '1px solid var(--line)',
          }}>
            <div>
              <span className="title-sm">隐患明细</span>
              <span className="caption" style={{ marginLeft: 12 }}>按严重程度排序 · 共 {total} 项</span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {['全部', '高', '中', '低'].map((t, i) => (
                <button key={i}
                  className={'btn ' + (i === 0 ? 'btn-secondary' : 'btn-ghost')}
                  style={{ padding: '8px 14px', fontSize: 13 }}>
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div style={{ padding: '0 28px' }}>
            {hazards.map((h, i) => (
              <HazardItem key={i} hazard={h} index={i + 1} />
            ))}
          </div>
        </div>

        {/* Sign-off */}
        <div className="dt-grid-signoff">
          {[
            { role: '安全员', name: '王立', status: '已签字', signed: true },
            { role: '班组长', name: '—',    status: '待签字', signed: false },
            { role: '项目经理', name: '—',  status: '待签字', signed: false },
          ].map((s, i) => (
            <div key={i} className="card" style={{ padding: 20 }}>
              <span className="caption">{s.role}</span>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
                <span className="title-sm" style={{ fontSize: 17 }}>{s.name}</span>
                {s.signed
                  ? <SeverityPill level="low" /> 
                  : <span className="sev" data-sev="none">待签字</span>}
              </div>
              <div style={{
                marginTop: 16, paddingTop: 16,
                borderTop: '1px dashed var(--line-2)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <span className="caption mono">{s.signed ? '2026·05·21 14:32' : '—'}</span>
                {!s.signed && (
                  <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 12 }}>
                    提醒 →
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{
          marginTop: 40, paddingTop: 24,
          borderTop: '1px solid var(--line)',
          display: 'flex', justifyContent: 'space-between',
          color: 'var(--ink-3)', fontSize: 12,
        }}>
          <span>Safety Scout · v0.3.1</span>
          <span className="mono">NO.2026-05-21-3742 · 报告完</span>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { DesktopReport });
