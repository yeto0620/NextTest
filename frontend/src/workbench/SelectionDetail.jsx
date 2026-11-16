import React from 'react'
import { Columns2, LockKeyhole, ShieldCheck } from 'lucide-react'
import { controlEntries, number } from './data'
import { useDataset, labelFor, unitFor } from './dataset'

function ControlGrid({ controls, includeAge = true }) {
  const meta = useDataset()
  return <dl className="nt-control-grid">
    {controlEntries(controls, includeAge).map(([key, value]) => <div key={key}><dt>{labelFor(meta, key)}</dt><dd>{number(value, 2)} <small>{unitFor(meta, key)}</small></dd></div>)}
  </dl>
}

export default function SelectionDetail({ selection, candidate, observed, view, mode, compareIds, onCompare }) {
  const meta = useDataset()
  if (!selection) return <aside className="nt-detail nt-detail-empty"><ShieldCheck size={18} /><strong>未选择记录</strong><p>点选一个方案查看详情。</p></aside>
  if (selection.kind === 'observed' && observed) return <aside className="nt-detail">
    <div className="nt-detail-head"><span className="nt-kicker">训练记录</span><span className="nt-state nt-state-known">已知实测</span></div>
    <h3>{observed._row_id}</h3>
    <div className="nt-detail-strong"><span>已观测 {meta.target.displayName}</span><strong>{number(observed[meta.target.key], 2)} <em>{meta.target.unit || 'unit not supplied'}</em></strong></div>
    <ControlGrid controls={Object.fromEntries(Object.entries(observed).filter(([key]) => key !== '_row_id' && key !== 'CompressiveStrength'))} />
    <footer><span>训练集 · 实测</span></footer>
  </aside>
  if (!candidate) return <aside className="nt-detail nt-detail-empty"><ShieldCheck size={18} /><strong>方案数据不可用</strong><p>请稍后重试。</p></aside>
  const isCompare = compareIds.includes(candidate.row_id)
  const isPending = view?.pending?.row_id === candidate.row_id
  return <aside className="nt-detail">
    <div className="nt-detail-head"><span className="nt-kicker">候选方案</span><span className={`nt-state ${isPending ? 'nt-state-pending' : 'nt-state-open'}`}>{isPending ? '预测已保存' : '结果未看'}</span></div>
    <h3>{candidate.row_id}</h3>
    <div className="nt-detail-strong"><span>模型预测 {meta.target.displayName}</span><strong>{number(isPending ? view.pending.prediction : candidate.prediction, 2)} <em>{meta.target.unit || 'unit not supplied'}</em></strong></div>
    <div className="nt-detail-pair">
      <div><span>模型分歧</span><strong>{number(isPending ? view.pending.disagreement : candidate.disagreement, 2)} <small>{meta.target.unit || ''}</small></strong></div>
      <div><span>{meta.target.displayName}实测</span><strong className="nt-missing">— <small>揭晓后显示</small></strong></div>
    </div>
    <ControlGrid controls={isPending ? view.pending.controls : candidate.controls} />
    {isPending && <p className="nt-detail-note"><LockKeyhole size={13} /> 已锁定，等待揭晓。</p>}
    <footer>
      <span>{view ? '当前项目' : '仅预览'}</span>
      <button type="button" className="nt-link-button" onClick={() => onCompare(candidate.row_id)} disabled={isCompare}>
        <Columns2 size={13} /> {isCompare ? '已在对比' : '加入对比'}
      </button>
    </footer>
    {mode === 'research' && <details className="nt-detail-research"><summary>数据说明</summary><div><span>来源</span><code>candidate_pool_no_labels</code><span>标签隔离</span><code>target / {meta.target.key} 不进入响应</code></div></details>}
  </aside>
}
