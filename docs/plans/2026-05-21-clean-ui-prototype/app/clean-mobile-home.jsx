// Clean & Minimal — mobile home, refactored to expose content separately
// so it can be rendered inside iOS frame OR a tablet/responsive wrapper.

function MobileHomeContent({ insideDevice = false }) {
  return (
    <div className="clean mobile-shell" style={{
      paddingTop: insideDevice ? 54 : 0,
      paddingBottom: insideDevice ? 32 : 0,
      minHeight: '100%',
    }}>
      {/* Brand bar */}
      <div className="appbar" style={{ paddingTop: 8 }}>
        <Brand />
        <div className="avatar">王</div>
      </div>

      {/* Hero */}
      <div style={{ padding: '32px 24px 24px' }}>
        <span className="eyebrow">AI 现场巡检</span>
        <h1 className="title-xl" style={{ fontSize: 44, marginTop: 12, marginBottom: 0 }}>
          拍一张<br/>AI 找隐患
        </h1>
        <p className="body" style={{ marginTop: 14, marginBottom: 0 }}>
          上传施工现场照片，30 秒内得到结构化安全报告
        </p>
      </div>

      <div style={{ padding: '0 24px' }}>
        <Photo src={PHOTO_URLS.site1} ratio="4/3" overlay
               meta="上次巡检 · 北区 5F · 2h 前" />
      </div>

      <div style={{ padding: '24px 24px 0' }}>
        <button className="btn-hero">
          <span className="btn-hero-text">
            <span className="btn-hero-title">开始巡检</span>
            <span className="btn-hero-sub">拍照 · 上传 · 等待报告</span>
          </span>
          <span className="btn-hero-icon"><Icon name="camera" size={22} color="#fff" /></span>
        </button>
        <button className="btn btn-ghost btn-block" style={{ marginTop: 8 }}>
          <Icon name="image" size={18} /> 从相册选择
        </button>
      </div>

      <div style={{ padding: '32px 24px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
          <span className="title-sm" style={{ fontSize: 16 }}>今日巡检</span>
          <span className="caption">查看全部 →</span>
        </div>
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            <Stat num="12" label="次巡检" />
            <Stat num="03" label="高风险" tone="high" />
            <Stat num="05" label="中风险" tone="med" />
          </div>
        </div>
      </div>

      <div style={{ flex: 1 }} />
    </div>
  );
}

function MobileHome() {
  return (
    <IOSDevice width={390} height={844} dark={false}>
      <MobileHomeContent insideDevice />
    </IOSDevice>
  );
}

Object.assign(window, { MobileHome, MobileHomeContent });
