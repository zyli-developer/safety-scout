// Clean & Minimal — shared components

// Unsplash construction photos. Reliable CDN; fall back to a tinted block.
const PHOTO_URLS = {
  hero:    'https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=1200&q=70&auto=format&fit=crop',
  worker:  'https://images.unsplash.com/photo-1581094288338-2314dddb7ece?w=1200&q=70&auto=format&fit=crop',
  site1:   'https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=1200&q=70&auto=format&fit=crop',
  site2:   'https://images.unsplash.com/photo-1590502593747-42a996133562?w=1200&q=70&auto=format&fit=crop',
  scaff:   'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=1200&q=70&auto=format&fit=crop',
  panel:   'https://images.unsplash.com/photo-1597166914903-d56f0b71f53e?w=1200&q=70&auto=format&fit=crop',
};

// ── Icons (heroicons-mini, stroked) ──
const I = {
  camera: 'M6.5 7a1.5 1.5 0 0 1 1.5-1.5h1l1-2h4l1 2h1A1.5 1.5 0 0 1 17.5 7v8.5A1.5 1.5 0 0 1 16 17H6a1.5 1.5 0 0 1-1.5-1.5V7zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  arrowRight: 'M5 12h14m-7-7 7 7-7 7',
  arrowUp: 'M12 19V5m-7 7 7-7 7 7',
  plus: 'M12 5v14m-7-7h14',
  check: 'M5 12l4 4 10-10',
  x: 'M6 6l12 12M6 18L18 6',
  chevronRight: 'm9 6 6 6-6 6',
  chevronLeft: 'm15 18-6-6 6-6',
  upload: 'M12 16V4m-5 5 5-5 5 5M4 20h16',
  image: 'M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6zm0 11 5-5 5 5 3-3 5 5',
  flash: 'M13 2 4 14h7l-2 8 9-12h-7l2-8z',
  dots: 'M6 12a1.5 1.5 0 1 0 0-.001M12 12a1.5 1.5 0 1 0 0-.001M18 12a1.5 1.5 0 1 0 0-.001',
  search: 'm21 21-5.2-5.2M17 10A7 7 0 1 1 3 10a7 7 0 0 1 14 0z',
  share: 'M8 12V6a4 4 0 1 1 8 0v6M5 12h14l-1 8H6l-1-8z',
  download: 'M12 4v12m-5-5 5 5 5-5M4 20h16',
  spark: 'M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1M5.6 18.4l2.1-2.1m8.6-8.6 2.1-2.1',
  refresh: 'M3 12a9 9 0 0 1 14.85-6.85L21 8M3 16l3.15-2.85A9 9 0 0 0 21 8V3m0 13v5h-5',
};

function Icon({ name, size = 18, color = 'currentColor', strokeWidth = 1.8 }) {
  const d = I[name] || '';
  return (
    <svg className="icn" width={size} height={size} viewBox="0 0 24 24"
         fill="none" stroke={color} strokeWidth={strokeWidth}
         strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

// ── Brand mark ──
function Brand({ size = 'md' }) {
  const isLg = size === 'lg';
  return (
    <div className="brand" style={isLg ? { fontSize: 17 } : {}}>
      <div className="brand-mark" style={isLg ? { width: 32, height: 32, fontSize: 15 } : {}}>S</div>
      <span>Safety Scout</span>
    </div>
  );
}

// ── Photo ──
function Photo({ src, alt = '', ratio = '16/9', overlay = false, meta, height, className = '' }) {
  return (
    <div className={'photo ' + className} style={{ aspectRatio: height ? undefined : ratio, height }}>
      <img src={src} alt={alt} />
      {overlay && <div className="photo-overlay-grad" />}
      {meta && (
        <div className="photo-meta">
          <span className="dot" />
          <span>{meta}</span>
        </div>
      )}
    </div>
  );
}

// ── Severity pill ──
const SEV_TEXT = { high: '高风险', medium: '中风险', low: '低风险' };
function SeverityPill({ level, solid = false, count }) {
  const Cls = solid ? 'sev-solid' : 'sev';
  return (
    <span className={Cls} data-sev={level}>
      {!solid && <span className="sev-dot" />}
      {SEV_TEXT[level]}{count != null ? ` · ${count}` : ''}
    </span>
  );
}

// ── Hazard item — clean list row ──
function HazardItem({ hazard, index, showFix = true }) {
  const { severity, description, regulation, suggestion, category_name, category_code } = hazard;
  return (
    <div className="hazard">
      <div className="hazard-idx">{String(index).padStart(2, '0')}</div>
      <div className="hazard-body">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="hazard-cat">{category_name}</span>
          <SeverityPill level={severity} />
        </div>
        <div className="hazard-desc">{description}</div>
        <div className="hazard-meta">
          <span>{category_code}</span>
          {regulation && <>
            <span className="dot-sep">·</span>
            <span>{regulation}</span>
          </>}
        </div>
        {showFix && (
          <div className="hazard-fix">
            <span className="hazard-fix-label">整改建议</span>
            {suggestion}
          </div>
        )}
      </div>
      <div className="hazard-action">
        <button className="btn btn-ghost" style={{ padding: '8px 10px', borderRadius: 10 }}>
          <Icon name="chevronRight" size={16} />
        </button>
      </div>
    </div>
  );
}

// ── Stat block ──
function Stat({ num, label, tone }) {
  return (
    <div className="stat">
      <span className={'num ' + (tone || '')}>{num}</span>
      <span className="lbl">{label}</span>
    </div>
  );
}

// ── Alarm ──
function AlarmBox({ children }) {
  return (
    <div className="alarm">
      <span className="alarm-icon">!</span>
      <div className="alarm-text">
        <strong>立即处置 · </strong>{children}
      </div>
    </div>
  );
}

// ── Progress ring ──
function ProgressRing({ pct = 0, label }) {
  const r = 38;
  const c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  return (
    <div className="progress-ring">
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={r} className="ring-track" strokeWidth="6" fill="none" />
        <circle cx="44" cy="44" r={r} className="ring-fill"
                strokeWidth="6" fill="none" strokeLinecap="round"
                strokeDasharray={c} strokeDashoffset={off} />
      </svg>
      <div className="ring-text">{label}</div>
    </div>
  );
}

// ── Step list ──
function StepList({ steps, currentStep }) {
  return (
    <div className="step-list">
      {steps.map((s, i) => {
        const state = i + 1 < currentStep ? 'done'
                    : i + 1 === currentStep ? 'active' : 'pending';
        return (
          <div className="step" key={i} data-state={state}>
            <span className="check">{state === 'done' ? '✓' : String(i + 1).padStart(2, '0')}</span>
            <span className="step-label">{s}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Top nav (desktop) ──
function TopNav({ activeTab = 'inspect', actions, user = '王立' }) {
  const tabs = [
    { id: 'inspect', label: '巡检' },
    { id: 'reports', label: '报告' },
    { id: 'team',    label: '班组' },
    { id: 'setting', label: '设置' },
  ];
  return (
    <div className="topnav">
      <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
        <Brand />
        <div className="nav-links">
          {tabs.map(t => (
            <div key={t.id} className={'nav-link ' + (t.id === activeTab ? 'active' : '')}>
              {t.label}
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {actions}
        <button className="btn btn-ghost" style={{ padding: 8, borderRadius: 999 }}>
          <Icon name="search" size={18} />
        </button>
        <div className="avatar">{user[0]}</div>
      </div>
    </div>
  );
}

// ── App bar (mobile) ──
function AppBar({ title, left, right, backless = false }) {
  return (
    <div className="appbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {!backless && (
          <button className="appbar-back" aria-label="返回">
            <Icon name="chevronLeft" size={18} />
          </button>
        )}
        {left}
        {title && <span className="appbar-title">{title}</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {right}
      </div>
    </div>
  );
}

Object.assign(window, {
  PHOTO_URLS, Icon, Brand, Photo, SeverityPill, SEV_TEXT,
  HazardItem, Stat, AlarmBox, ProgressRing, StepList,
  TopNav, AppBar,
});
