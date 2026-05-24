// Clean & Minimal — mobile report. Content factored out for reuse.

function MobileReportContent({ severity = 'high', insideDevice = false }) {
  const hazards = SAMPLE_HAZARDS;
  const total = hazards.length;
  const counts = {
    high: hazards.filter(h => h.severity === 'high').length,
    medium: hazards.filter(h => h.severity === 'medium').length,
    low: hazards.filter(h => h.severity === 'low').length,
  };

  return (
    <div className="clean mobile-shell" style={{
      paddingTop: insideDevice ? 54 : 0,
      minHeight: '100%',
    }}>
      <AppBar
        title="巡检报告"
        right={
          <>
            <button className="appbar-icon"><Icon name="share" size={16} /></button>
            <button className="appbar-icon"><Icon name="dots" size={16} /></button>
          </>
        }
      />

      <div style={{ padding: '8px 20px 0' }}>
        <Photo src={PHOTO_URLS.scaff} ratio="4/3" overlay
               meta="NO.2026-05-21-3742 · 北区 5F" />
      </div>

      <div style={{ padding: '20px 20px 0' }}>
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
            <div>
              <span className="eyebrow">检出隐患</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 6 }}>
                <span className="title-xl" style={{ fontSize: 56 }}>{total}</span>
                <span className="body-sm muted">项</span>
              </div>
            </div>
            <SeverityPill level={severity} solid />
          </div>

          <p className="body-sm" style={{ marginTop: 16, marginBottom: 0 }}>
            {SAMPLE_REPORT.summary}
          </p>

          <div style={{
            display: 'flex', gap: 8,
            marginTop: 16, paddingTop: 16,
            borderTop: '1px solid var(--line)',
          }}>
            <SeverityPill level="high" count={counts.high} />
            <SeverityPill level="medium" count={counts.medium} />
            <SeverityPill level="low" count={counts.low} />
          </div>
        </div>
      </div>

      <div style={{ padding: '16px 20px 0' }}>
        <AlarmBox>{SAMPLE_REPORT.plain_warning}</AlarmBox>
      </div>

      <div style={{ padding: '24px 20px 16px' }}>
        <span className="title-sm" style={{ display: 'block', marginBottom: 8 }}>隐患明细</span>
        <span className="caption">按严重程度排序</span>

        <div style={{ marginTop: 12 }}>
          {hazards.map((h, i) => (
            <HazardItem key={i} hazard={h} index={i + 1} />
          ))}
        </div>
      </div>

      <div style={{
        position: 'sticky', bottom: 0,
        padding: '12px 20px 28px',
        background: 'rgba(250,250,248,0.92)',
        backdropFilter: 'blur(12px)',
        borderTop: '1px solid var(--line)',
        display: 'flex', gap: 8,
      }}>
        <button className="btn btn-secondary" style={{ flex: 1 }}>
          <Icon name="download" size={16} /> 导出 PDF
        </button>
        <button className="btn btn-primary" style={{ flex: 1.4 }}>
          <Icon name="share" size={16} /> 转派班组
        </button>
      </div>
    </div>
  );
}

function MobileReport({ severity = 'high' }) {
  return (
    <IOSDevice width={390} height={844} dark={false}>
      <MobileReportContent severity={severity} insideDevice />
    </IOSDevice>
  );
}

Object.assign(window, { MobileReport, MobileReportContent });
