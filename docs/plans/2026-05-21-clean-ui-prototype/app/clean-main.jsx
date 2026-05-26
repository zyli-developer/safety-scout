// Clean — design canvas root.

const TWEAK_DEFAULS = /*EDITMODE-BEGIN*/{
  "reportSeverity": "high"
}/*EDITMODE-END*/;

function CleanApp() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULS);

  return (
    <>
      <DesignCanvas>
        <DCSection
          id="mobile"
          title="移动端 · 小程序 / H5"
          subtitle="拍摄 → 等待 → 报告 · 三步极简流"
        >
          <DCArtboard id="m-home" label="01 · 首页" width={390} height={900}>
            <MobileHome />
          </DCArtboard>

          <DCArtboard id="m-scan" label="02 · 等待 / 分析中" width={390} height={900}>
            <MobileScan />
          </DCArtboard>

          <DCArtboard id="m-report" label="03 · 报告 / 隐患明细" width={390} height={2050}>
            <MobileReport severity={t.reportSeverity} />
          </DCArtboard>
        </DCSection>

        <DCSection
          id="desktop"
          title="桌面端 · PC Web"
          subtitle="安全员办公位 · 大留白 · 真实工地图主导"
        >
          <DCArtboard id="d-home" label="04 · 工作台 / 上传" width={1280} height={920}>
            <DesktopHome />
          </DCArtboard>

          <DCArtboard id="d-report" label="05 · 报告 / 详情" width={1280} height={2050}>
            <DesktopReport severity={t.reportSeverity} />
          </DCArtboard>
        </DCSection>

        <DCSection
          id="responsive"
          title="自适应验证 · Responsive Breakpoints"
          subtitle="同一套组件在不同容器宽度下的响应 · 用 @container queries 驱动"
        >
          <DCArtboard id="r-tablet-home" label="06 · 平板 768 · 首页居中 max-width 640" width={768} height={1020}>
            <div style={{ minHeight: 1020, background: 'var(--bg)' }}>
              <MobileHomeContent />
            </div>
          </DCArtboard>

          <DCArtboard id="r-tablet-report" label="07 · 平板 768 · 报告居中" width={768} height={1800}>
            <div style={{ minHeight: 1800, background: 'var(--bg)' }}>
              <MobileReportContent severity={t.reportSeverity} />
            </div>
          </DCArtboard>

          </DCArtboard>
        </DCSection>

        <DCPostIt x={40} y={40} w={300}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Clean &amp; Minimal · 第三版</div>
          <div style={{ fontSize: 12, lineHeight: 1.55 }}>
            浅色 · 暖白底 · 单一安全橙 · 真实工地照片占主导 · 严重度仅用 pill。
            扔掉文档感和 HUD 感，回归现代 app 的克制美学。
          </div>
        </DCPostIt>
      </DesignCanvas>

      <TweaksPanel title="Tweaks">
        <TweakSection label="REPORT">
          <TweakRadio
            label="风险等级"
            value={t.reportSeverity}
            options={[
              { value: 'high',   label: '高' },
              { value: 'medium', label: '中' },
              { value: 'low',    label: '低' },
            ]}
            onChange={(v) => setTweak('reportSeverity', v)}
          />
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<CleanApp />);
