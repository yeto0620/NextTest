import React, { useEffect, useRef } from 'react'
import { ArrowRight, Beaker, Eye, LockKeyhole, MonitorPlay, Orbit, X } from 'lucide-react'
import ObservationPlate from './ObservationPlate'
import { number, statusLabel, strategyLabel } from './data'
import { useDataset } from './dataset'

function stageFor(view) {
  if (view?.pending) return ['03', '封存']
  if (view?.history?.length) return ['04', '更新']
  return ['01', '观测']
}

export default function PresentationStage({ open, onClose, landscape, view, preview, selectedCandidate, compareCandidate, selection, onSelectObserved, onNavigate }) {
  const meta = useDataset()
  const closeRef = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = event => { if (event.key === 'Escape') onClose() }
    const timer = window.setTimeout(() => closeRef.current?.focus(), 30)
    window.addEventListener('keydown', onKeyDown)
    return () => { window.clearTimeout(timer); window.removeEventListener('keydown', onKeyDown) }
  }, [open, onClose])
  if (!open) return null
  const snapshot = view?.snapshot
  const pending = view?.pending
  const last = view?.history?.at(-1)
  const [stageCode, stageName] = stageFor(view)
  const candidate = pending || selectedCandidate || preview?.selected || null
  const enter = id => { onClose(); onNavigate(id) }
  return <div className="nt-stage-layer" role="dialog" aria-modal="true" aria-labelledby="nt-stage-title">
    <div className="nt-stage-shell">
      <header className="nt-stage-head"><div className="nt-stage-brand"><MonitorPlay size={17} /><span>NextTest</span><small>LIVE DEMO STAGE</small></div><div className="nt-stage-state"><i /><span>{stageCode}</span><strong>{stageName}</strong></div><button ref={closeRef} type="button" className="nt-icon-button" onClick={onClose} aria-label="退出演示模式"><X size={16} /></button></header>
      <main className="nt-stage-main">
        <section className="nt-stage-hero"><div className="nt-stage-copy"><span className="nt-kicker">HISTORICAL EXPERIMENT REPLAY</span><h1 id="nt-stage-title">让证据，<em>决定下一步。</em></h1><p>每次只揭示一条历史记录。预测先封存，结果后出现。</p><div className="nt-stage-rail" aria-label="回放进度"><span className="is-ready"><i />观测</span><b /><span className={candidate ? 'is-ready' : ''}><i />候选</span><b /><span className={pending ? 'is-ready' : ''}><i />封存</span><b /><span className={last ? 'is-ready' : ''}><i />揭示</span></div></div>
          <ObservationPlate landscape={landscape} selectedCandidate={candidate} compareCandidate={compareCandidate} selection={selection} onSelectObserved={onSelectObserved} />
        </section>
        <aside className="nt-stage-readout"><span className="nt-kicker">CURRENT READOUT</span>{pending ? <><div className="nt-stage-readout-title"><LockKeyhole size={16} /><strong>预测已封存</strong></div><p>历史实测仍隐藏；演示不会提前读取结果。</p><dl><div><dt>候选</dt><dd>{pending.row_id}</dd></div><div><dt>预测</dt><dd>{number(pending.prediction, 2)} {meta.target.unit || ''}</dd></div><div><dt>策略</dt><dd>{strategyLabel(snapshot?.strategy)}</dd></div></dl></> : last ? <><div className="nt-stage-readout-title"><Eye size={16} /><strong>最新揭示</strong></div><p>只显示已经由当前项目公开的历史实测。</p><dl><div><dt>候选</dt><dd>{last.row_id}</dd></div><div><dt>预测</dt><dd>{number(last.prediction, 2)} {meta.target.unit || ''}</dd></div><div><dt>实测</dt><dd>{number(last.revealed_target, 2)} {meta.target.unit || ''}</dd></div><div><dt>误差</dt><dd>{number(last.absolute_error, 2)} {meta.target.unit || ''}</dd></div></dl></> : <><div className="nt-stage-readout-title"><Orbit size={16} /><strong>准备观察</strong></div><p>当前没有封存的建议。先进入候选空间或实验台。</p><dl><div><dt>观测</dt><dd>{landscape?.rows?.length ?? '—'} 条</dd></div><div><dt>候选</dt><dd>{snapshot?.candidate_count ?? preview?.candidate_count ?? '—'} 条</dd></div><div><dt>状态</dt><dd>{snapshot ? statusLabel(snapshot.status) : '未创建项目'}</dd></div></dl></>}
          <div className="nt-stage-actions"><button type="button" className="nt-primary" onClick={() => enter('bench')}><Beaker size={15} /> 进入实验 <ArrowRight size={15} /></button><button type="button" className="nt-secondary-button" onClick={() => enter('atlas')}><Orbit size={15} /> 查看候选</button></div>
          <footer>历史回放，不是新物理实验；模型预测不是实测。</footer>
        </aside>
      </main>
    </div>
  </div>
}
