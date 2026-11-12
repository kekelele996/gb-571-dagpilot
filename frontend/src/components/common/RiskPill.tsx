import { RISK_CLASS, RISK_LABELS, type RiskLevel } from '../../constants/enums';

export default function RiskPill({ level, label }: { level: string; label?: string }) {
  const key = (level in RISK_LABELS ? level : 'no_sla') as RiskLevel;
  return <span className={RISK_CLASS[key]}>{label || RISK_LABELS[key]}</span>;
}
