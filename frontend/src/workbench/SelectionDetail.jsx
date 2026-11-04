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
  if (!selection) return <aside className="nt-detail nt-detail-empty"><ShieldCheck size={18} /><strong>未选择记录</strong><p>在航图、表格或已观测记录中选择一个对象；所有视图共享同一个选择状态。</p></aside>
  if (selection.kind === 'observed' && observed) return <aside className="nt-detail">
    <div className="nt-detail-head"><span className="nt-kicker">OBSERVED RECORD</span><span className="nt-state nt-state-known">已知实测</span></div>
    <h3>{observed._row_id}</h3>
    <p className="nt-detail-lead">这条记录已经存在于训练数据中。它是实测值，不是模型预测。</p>
    <div className="nt-detail-strong"><span>已观测 {meta.target.displayName}</span><strong>{number(observed[meta.target.key], 2)} <em>{meta.target.unit || 'unit not supplied'}</em></strong></div>
    <ControlGrid controls={Object.fromEntries(Object.entries(observed).filter(([key]) => key !== '_row_id' && key !== 'CompressiveStrength'))} />
    <footer><span>来源：训练记录</span><span>单位：{meta.features.map(f => f.unit || 'unit not supplied').join(' / ')}</span></footer>
  </aside>
  if (!candidate) return <aside className="nt-detail nt-detail-empty"><ShieldCheck size={18} /><strong>方案数据不可用</strong><p>后端没有返回方案投影。界面不会用 mock 数值补位。</p></aside>
  const isCompare = compareIds.includes(candidate.row_id)
  const isPending = view?.pending?.row_id === candidate.row_id
  return <aside className="nt-detail">
    <div className="nt-detail-head"><span className="nt-kicker">CANDIDATE / NO LABEL</span><span className={`nt-state ${isPending ? 'nt-state-pending' : 'nt-state-open'}`}>{isPending ? '预测已保存' : '历史结果未公布'}</span></div>
    <h3>{candidate.row_id}</h3>
    <p className="nt-detail-lead">方案来自冻结的历史方案池。这里只有配方与模型预测；真实强度不在浏览器中。</p>
    <div className="nt-detail-strong"><span>模型预测 {meta.target.displayName}</span><strong>{number(isPending ? view.pending.prediction : candidate.prediction, 2)} <em>{meta.target.unit || 'unit not supplied'}</em></strong></div>
    <div className="nt-detail-pair">
      <div><span>预测差值异</span><strong>{number(isPending ? view.pending.disagreement : candidate.disagreement, 2)} <small>{meta.target.unit || ''}</small></strong></div>
      <div><span>{meta.target.displayName}实测</span><strong className="nt-missing">— <small>reveal 后才有</small></strong></div>
    </div>
    <ControlGrid controls={isPending ? view.pending.controls : candidate.controls} />
    {isPending && <p className="nt-detail-note"><LockKeyhole size={13} /> 这条方案已被当前项目锁定；只有确认公布后才会读取历史实测。</p>}
    <footer>
      <span>策略：{view ? '当前项目' : '预览'}</span>
      <button type="button" className="nt-link-button" onClick={() => onCompare(candidate.row_id)} disabled={isCompare}>
        <Columns2 size={13} /> {isCompare ? '已在对比' : '加入并排对比'}
      </button>
    </footer>
    {mode === 'research' && <div className="nt-detail-research"><span>投影来源</span><code>candidate_pool_no_labels</code><span>不变量</span><code>target / {meta.target.key} 不进入响应</code></div>}
  </aside>
}
