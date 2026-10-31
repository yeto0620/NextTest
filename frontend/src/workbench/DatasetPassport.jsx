import React from 'react'
import { Fingerprint, GitCompareArrows, LockKeyhole, X } from 'lucide-react'
import { useDataset } from './dataset'

export default function DatasetPassport({ open, dataset, onClose, onCompare }) {
  const meta = useDataset()
  if (!open) return null
  const units = dataset?.units || meta.units || {}
  const features = meta.features || []
  const sha = dataset?.sha256 || {}
  return <div className="nt-passport-layer" role="dialog" aria-modal="true" aria-labelledby="nt-passport-title">
    <button type="button" className="nt-passport-backdrop" onClick={onClose} aria-label="关闭 Dataset Passport" />
    <aside className="nt-passport-modal">
      <header><div><span className="nt-kicker">DATASET PASSPORT / 只读样本护照</span><h2 id="nt-passport-title">{meta.displayName}</h2><p>{meta.shortId || '—'} · {meta.isCustom ? 'LOCAL DATASET' : 'DEMO DATASET'} · 冻结后不可原地修改</p></div><button type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭"><X size={15} /></button></header>
      <div className="nt-passport-stamp"><Fingerprint size={16} /><span>{dataset?.gate_status || (meta.isCustom ? '—' : 'DEMO')}</span><small>{dataset?.warning_count != null ? `${dataset.warning_count} warnings acknowledged` : 'unit_not_verified'}</small></div>
      <dl><dt>目标</dt><dd>{meta.target.displayName} <code>{meta.target.key}</code> · {meta.target.unit || 'unit not supplied'}</dd><dt>特征</dt><dd>{features.length} 列 · {features.map(f => f.displayName).join(' / ') || '—'}</dd><dt>数据 SHA</dt><dd><code>{sha.input || sha.source || '—'}</code></dd><dt>schema SHA</dt><dd><code>{sha.schema || '—'}</code></dd><dt>split SHA</dt><dd><code>{sha.split || '—'}</code></dd><dt>切分</dt><dd>{dataset?.counts ? `${dataset.counts.train} / ${dataset.counts.candidate} / ${dataset.counts.test} · ${dataset.counts.groups} groups` : '—'}</dd><dt>单位声明</dt><dd>用户声明；unit_not_verified；不做自动换算</dd><dt>历史回放</dt><dd>是 · 不是新物理实验</dd></dl>
      <footer><span><LockKeyhole size={12} /> 只读证据；修改角色必须新建 intake。</span>{onCompare && <button type="button" className="nt-secondary-button" onClick={onCompare}><GitCompareArrows size={12} /> 在此数据上建立策略比较</button>}</footer>
    </aside>
  </div>
}
