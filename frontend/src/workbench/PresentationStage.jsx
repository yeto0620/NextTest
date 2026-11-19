import React, { useEffect, useRef } from 'react'
import { ArrowRight, Beaker, Eye, LockKeyhole, MonitorPlay, Orbit, X } from 'lucide-react'
import ObservationPlate from './ObservationPlate'
import { number, statusLabel, strategyLabel } from './data'
import { useDataset } from './dataset'

function stageFor(view) {
  if (view?.pending) return ['03', '实验']
  if (view?.history?.length) return ['04', '结果']
  return ['01', '数据']
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
  const talk = pending
    ? '预测已经保存，但历史结果还没有出现。接下来我只查看这一条历史记录。'
    : last
      ? '预测、结果和误差都在这里。这一轮结束，同时留下可复核的记录。'
      : '先看历史数据和候选配方，再决定下一条要锁定哪一组实验。'
  const hint = pending ? '下一步：去实验台，点击“揭晓历史结果”。' : last ? '下一步：打开结果页，看本轮总结。' : '下一步：查看候选，或直接开始一次演示。'
  const primaryLabel = pending ? '去实验台揭晓' : last ? '查看本轮总结' : '开始演示'

  return <div className="nt-stage-layer" role="dialog" aria-modal="true" aria-labelledby="nt-stage-title">
    <div className="nt-stage-shell">
      <header className="nt-stage-head"><div className="nt-stage-brand"><MonitorPlay size={17} /><span>NextTest 智试</span><small>3 分钟演示</small></div><div className="nt-stage-state"><i /><span>{stageCode}</span><strong>{stageName}</strong></div><button ref={closeRef} type="button" className="nt-icon-button" onClick={onClose} aria-label="退出演示模式"><X size={16} /></button></header>
      <main className="nt-stage-main">
        <section className="nt-stage-hero"><div className="nt-stage-copy"><span className="nt-kicker">MATERIAL FORMULATION / DECISION DEMO</span><h1 id="nt-stage-title">下一批实验，<em>先做哪几组？</em></h1><p>用历史配方数据，演示如何从候选方案中选出下一批最值得做的实验。</p><div className="nt-stage-rail" aria-label="演示进度"><span className="is-ready"><i />数据</span><b /><span className={candidate ? 'is-ready' : ''}><i />方案</span><b /><span className={pending ? 'is-ready' : ''}><i />实验</span><b /><span className={last ? 'is-ready' : ''}><i />结果</span></div></div>
          <ObservationPlate landscape={landscape} selectedCandidate={candidate} compareCandidate={compareCandidate} selection={selection} onSelectObserved={onSelectObserved} />
        </section>
        <aside className="nt-stage-readout"><span className="nt-kicker">当前推荐 / CURRENT READOUT</span>{pending ? <><div className="nt-stage-readout-title"><LockKeyhole size={16} /><strong>预测已锁定</strong></div><p>历史结果仍隐藏；演示不会提前读取答案。</p><dl><div><dt>方案</dt><dd>{pending.row_id}</dd></div><div><dt>预测</dt><dd>{number(pending.prediction, 2)} {meta.target.unit || ''}</dd></div><div><dt>策略</dt><dd>{strategyLabel(snapshot?.strategy)}</dd></div></dl></> : last ? <><div className="nt-stage-readout-title"><Eye size={16} /><strong>本轮结果</strong></div><p>只显示当前项目已经查看过的历史结果。</p><dl><div><dt>方案</dt><dd>{last.row_id}</dd></div><div><dt>预测</dt><dd>{number(last.prediction, 2)} {meta.target.unit || ''}</dd></div><div><dt>实测</dt><dd>{number(last.revealed_target, 2)} {meta.target.unit || ''}</dd></div><div><dt>误差</dt><dd>{number(last.absolute_error, 2)} {meta.target.unit || ''}</dd></div></dl></> : <><div className="nt-stage-readout-title"><Orbit size={16} /><strong>准备开始</strong></div><p>先看数据与候选方案，再锁定一条预测。</p><dl><div><dt>观测</dt><dd>{landscape?.rows?.length ?? '—'} 条</dd></div><div><dt>方案</dt><dd>{snapshot?.candidate_count ?? preview?.candidate_count ?? '—'} 条</dd></div><div><dt>状态</dt><dd>{snapshot ? statusLabel(snapshot.status) : '未创建项目'}</dd></div></dl></>}
          <div className="nt-stage-talk"><span>演示提示</span><p>{talk}</p><small>{hint}</small></div>
          <div className="nt-stage-actions"><button type="button" className="nt-primary" onClick={() => enter(last ? 'trail' : 'bench')}><Beaker size={15} /> {primaryLabel} <ArrowRight size={15} /></button>{!last && <button type="button" className="nt-secondary-button" onClick={() => enter('atlas')}><Orbit size={15} /> 查看候选</button>}</div>
          <footer>历史数据回放 · 不是新实验 · 预测不是实测</footer>
        </aside>
      </main>
    </div>
  </div>
}
