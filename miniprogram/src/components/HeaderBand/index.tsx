/**
 * HeaderBand —— 顶部铭牌。
 *
 * 每个页面都用同一份 banner：左侧是品牌（拉丁 + 中文两行），右侧可选 identifier
 * (NO.xxx 编号) + 可选 subtitle (一般是时间戳)。底部 1px charcoal rule 把
 * banner 和页面其它内容分开。
 *
 * 没有交互、没有 mode 切换，就是一个静态文档表头。
 */
import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export interface HeaderBandProps {
  /** 编号 / 文档号；可选 (e.g. "NO.2026-05-20-0001") */
  identifier?: string;
  /** 副标 / 时间戳；可选 (e.g. "2026·05·20  14:32") */
  subtitle?: string;
}

export function HeaderBand({ identifier, subtitle }: HeaderBandProps) {
  return (
    <View className={styles.band}>
      <View className={styles.row}>
        <Text className={styles.brand}>SAFETY SCOUT</Text>
        {identifier && <Text className={styles.identifier}>{identifier}</Text>}
      </View>
      <View className={styles.row}>
        <Text className={styles.brandZh}>工地安全巡检系统</Text>
        {subtitle && <Text className={styles.subtitle}>{subtitle}</Text>}
      </View>
      <View className={styles.rule} />
    </View>
  );
}
