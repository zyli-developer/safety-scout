// Clean — desktop home screen.

function DesktopHome() {
  const recent = [
    { id: '2026-05-21-3742', site: '北区 5F 楼板', when: '14:30', sev: 'high',   count: 5 },
    { id: '2026-05-21-3741', site: '南区配电间',   when: '13:08', sev: 'medium', count: 3 },
    { id: '2026-05-21-3740', site: '东侧脚手架',   when: '11:42', sev: 'medium', count: 2 },
    { id: '2026-05-21-3739', site: '材料堆场',     when: '10:15', sev: 'low',    count: 1 },
  ];

  return (
    <div className="clean" style={{ minHeight: '100%', background: 'var(--bg)' }}>
      <TopNav activeTab="inspect" />

      <div className="dt-shell-home">
        {/* Page header */}
        <div className="dt-page-header">
          <div>
            <span className="eyebrow">SH-PD-JQ-001 · 上海·浦东金桥项目</span>
            <h1 className="title-lg" style={{ marginTop: 12, marginBottom: 0 }}>
              开始一次现场巡检
            </h1>
            <p className="body" style={{ marginTop: 10, marginBottom: 0, maxWidth: 520 }}>
              上传一张施工现场照片，AI 会在 30 秒内识别隐患、引用规范条款、给出可执行的整改建议。
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary">
              <Icon name="image" size={16} /> 历史报告
            </button>
            <button className="btn btn-primary">
              <Icon name="plus" size={16} /> 新建巡检
            </button>
          </div>
        </div>

        {/* Main layout: dropzone + sidebar */}
        <div className="dt-grid-home">
          {/* Dropzone card */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: 32, borderBottom: '1px solid var(--line)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span className="title-sm">上传现场照片</span>
                <span className="caption mono">JPG · PNG · HEIC · 最大 15MB</span>
              </div>
            </div>

            {/* The actual drop area, with a real photo as background to suggest "this is where photos go" */}
            <div style={{
              position: 'relative',
              minHeight: 380,
              background: 'var(--surface-2)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 16, padding: 32,
              cursor: 'pointer',
            }}>
              <div style={{
                width: 72, height: 72,
                borderRadius: '50%',
                background: 'var(--surface)',
                border: '1px solid var(--line)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: 'var(--shadow-sm)',
              }}>
                <Icon name="upload" size={28} color="var(--ink)" strokeWidth={1.6} />
              </div>
              <div style={{ textAlign: 'center' }}>
                <div className="title-md" style={{ fontSize: 22 }}>拖拽图片到此处</div>
                <div className="body-sm" style={{ marginTop: 6 }}>或点击选择文件 · 支持手机扫码上传</div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button className="btn btn-primary">
                  <Icon name="upload" size={16} /> 选择文件
                </button>
                <button className="btn btn-secondary">
                  <Icon name="camera" size={16} /> 手机扫码
                </button>
              </div>
            </div>

            {/* AI engine info strip */}
            <div style={{
              padding: '16px 32px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              borderTop: '1px solid var(--line)',
              background: 'var(--surface)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: 'var(--low)',
                  boxShadow: '0 0 0 4px rgba(47,132,84,0.15)',
                }} />
                <span className="body-sm">
                  <span style={{ color: 'var(--ink)', fontWeight: 500 }}>Claude Sonnet 4.5</span>
                  <span className="muted"> · 平均 29s · 今日 99.4% 可用</span>
                </span>
              </div>
              <span className="caption mono">v0.3.1</span>
            </div>
          </div>

          {/* Sidebar: Today + Recent */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="card">
              <span className="title-sm" style={{ display: 'block', marginBottom: 16 }}>今日巡检</span>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <Stat num="12" label="次巡检" />
                <Stat num="03" label="高风险" tone="high" />
                <Stat num="05" label="中风险" tone="med" />
                <Stat num="04" label="低风险" tone="low" />
              </div>
            </div>

            <div className="card" style={{ padding: 0 }}>
              <div style={{ padding: '20px 24px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span className="title-sm">最近巡检</span>
                <span className="caption" style={{ color: 'var(--accent)' }}>查看全部 →</span>
              </div>
              <div style={{ padding: '0 12px 12px' }}>
                {recent.map((r) => (
                  <div key={r.id} className="card-row" style={{ padding: '12px' }}>
                    <div style={{
                      width: 40, height: 40, borderRadius: 10,
                      background: 'var(--surface-2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: 'var(--ink-2)',
                    }}>
                      <Icon name="image" size={18} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className="body-sm" style={{ color: 'var(--ink)', fontWeight: 500 }}>{r.site}</span>
                        <SeverityPill level={r.sev} />
                      </div>
                      <div className="caption mono" style={{ marginTop: 2 }}>
                        NO.{r.id} · {r.when} · {r.count} 项隐患
                      </div>
                    </div>
                    <Icon name="chevronRight" size={16} color="var(--ink-3)" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { DesktopHome });
