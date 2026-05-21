/**
 * BigButton — clean-minimal 版本：薄壳代理到 Button variant="hero"。
 *
 * 旧 dossier 形态（朱红填充 + 等距字 Latin 副标 + glyph 槽位）已废弃；新版是
 * 安全橙 hero CTA + icon 圆 + 中文 title + 副文。保留 props API 让 pages/index
 * 调用方在 Slice 3 阶段无需改动。
 */
import { Button } from '../Button';
import type { IconName } from '../Icon';

export interface BigButtonProps {
  text: string;
  subtitle?: string;
  prefixGlyph?: IconName;
  onTap: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export function BigButton({
  text,
  subtitle,
  prefixGlyph,
  onTap,
  loading,
  disabled,
}: BigButtonProps) {
  return (
    <Button
      variant="hero"
      title={text}
      subtitle={subtitle}
      icon={prefixGlyph}
      onTap={onTap}
      loading={loading}
      disabled={disabled}
    />
  );
}
