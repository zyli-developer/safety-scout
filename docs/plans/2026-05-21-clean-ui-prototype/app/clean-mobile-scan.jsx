// Clean — mobile scanning screen.

function MobileScan() {
  const pct = 62;
  return (
    <IOSDevice width={390} height={844} dark={false}>
      <div className="clean" style={{ minHeight: '100%', display: 'flex', flexDirection: 'column', paddingTop: 54, background: 'var(--bg)' }}>
        <AppBar
          title="正在分析"
          right={<button className="appbar-icon"><Icon name="x" size={16} /></button>}
        />

        {/* Photo preview */}
        <div style={{ padding: '8px 24px 0' }}>
          <Photo src={PHOTO_URLS.scaff} ratio="4/3" overlay
                 meta="拍摄于 14:30:12 · 北区 5F" />
        </div>

        {/* Progress card */}
        <div style={{ padding: '24px 24px 0' }}>
          <div className="card" style={{ padding: 24, display: 'flex', alignItems: 'center', gap: 20 }}>
            <ProgressRing pct={pct} label={`${pct}%`} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="title-sm" style={{ fontSize: 17 }}>AI 正在分析现场</div>
              <div className="caption" style={{ marginTop: 4 }}>
                <span className="mono">CLAUDE 4.5</span> · 预计 30 秒内完成
              </div>
              <div className="caption mono" style={{ marginTop: 8, color: 'var(--accent)' }}>
                已用 23s
              </div>
            </div>
          </div>
        </div>

        {/* Steps */}
        <div style={{ padding: '24px 24px 0' }}>
          <span className="eyebrow" style={{ display: 'block', marginBottom: 12 }}>分析进度</span>
          <StepList
            steps={[
              '图像上传完成',
              'AI 视觉解析中',
              '生成结构化报告',
            ]}
            currentStep={2}
          />
        </div>

        {/* Tip while waiting */}
        <div style={{ padding: '32px 24px 0', marginTop: 'auto', marginBottom: 40 }}>
          <div className="card" style={{ background: 'var(--surface-2)', border: 'none', padding: 16 }}>
            <span className="eyebrow" style={{ display: 'block', marginBottom: 6 }}>提示</span>
            <span className="body-sm">分析期间可以保持页面打开，完成后会自动跳转到报告页。</span>
          </div>
        </div>
      </div>
    </IOSDevice>
  );
}

Object.assign(window, { MobileScan });
