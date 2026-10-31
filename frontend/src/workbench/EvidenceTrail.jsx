import React, { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, Check, ChevronDown, CircleDashed, Download, GitBranch, LockKeyhole, ScanLine, ShieldAlert } from 'lucide-react'
import { STRATEGY_META, number, statusLabel, text } from './data'
import { useDataset, labelFor, unitFor } from './dataset'
import ScienceScenes from './ScienceScenes'

const STAGES = [
  ['data', '数据进入', 'SOURCE IN'],
  ['fields', '字段确认', 'SCHEMA'],
  ['training', '模型训练', 'TRAIN'],
  ['compare', '候选比较', 'COMPARE'],
  ['seal', '预测封存', 'SEAL'],
  ['reveal', '结果揭示', 'REVEAL'],
  ['update', '判断更新', 'UPDATE'],
]

function buildNodes(view, landscape, preview, meta) {
  const snapshot = view?.snapshot
  const pending = view?.pending
  const history = view?.history || []
  const observedKeys = Object.keys(landscape?.rows?.[0] || {}).filter(key => !['_row_id', 'CompressiveStrength'].includes(key))
  const candidateKeys = Object.keys(preview?.rows?.[0]?.controls || {}).filter(key => key !== 'Age')
  const controls = candidateKeys.length ? candidateKeys : observedKeys
  const lastHistory = history.at(-1)
  const pendingRecord = pending ? {
    row_id: pending.row_id, prediction: pending.prediction, disagreement: pending.disagreement,
    controls: pending.controls, strategy: snapshot?.strategy,
  } : null
  return STAGES.map(([id, title, code], index) => {
    let status = 'waiting', value = '—', detail = ''
    if (id === 'data') {
      status = landscape?.rows?.length ? 'done' : 'waiting'
      value = landscape?.rows?.length ? `${landscape.rows.length} 条训练记录` : '未加载'
      detail = landscape?.split_sha256 ? `split ${landscape.split_sha256}` : '后端没有返回已观测数据。'
    } else if (id === 'fields') {
      status = controls.length ? 'done' : 'waiting'
      value = controls.length ? `${controls.length} 个 feature · ${meta.features.length} 列已定义` : '不可用'
      detail = controls.length ? `${controls.map(key => labelFor(meta, key)).join(' · ')}；目标列在服务端固定，前端不读取候选标签。` : '没有候选字段投影。'
    } else if (id === 'training') {
      status = snapshot ? 'done' : 'waiting'
      value = snapshot ? `${snapshot.initial_model_sha?.slice(0, 12) || '—'}…` : '尚未创建项目'
      detail = snapshot ? `初始模型 ${text(snapshot.initial_model_sha)}；当前 ${text(snapshot.current_model_sha)}` : '创建项目后才有模型版本。'
    } else if (id === 'compare') {
      const count = history.length + (pending ? 1 : 0)
      status = count ? 'done' : 'waiting'
      value = count ? `${count} 条已保存候选` : '尚无候选'
      detail = pending ? `待确认：${pending.row_id}（${STRATEGY_META[snapshot?.strategy]?.label || '—'}）` : lastHistory ? `最近：${lastHistory.row_id}` : '还没有锁定候选。'
    } else if (id === 'seal') {
      status = pending || history.length ? 'done' : 'waiting'
      value = pending ? `${number(pending.prediction, 2)} ${meta.target.unit || ''}` : lastHistory ? `${number(lastHistory.prediction, 2)} ${meta.target.unit || ''}` : '—'
      detail = pending ? `${pending.row_id} 的预测已写入项目事件；真实值仍隐藏。` : lastHistory ? `最近一轮 ${lastHistory.row_id} 的预测已先于揭示保存。` : '预测只在项目事件中封存。'
    } else if (id === 'reveal') {
      status = history.length ? 'done' : 'waiting'
      value = history.length ? `${history.length} 条历史实测` : '尚未揭示'
      detail = lastHistory ? `最近 ${lastHistory.row_id}：${number(lastHistory.revealed_target, 2)} ${meta.target.unit || ''}；绝对误差 ${number(lastHistory.absolute_error, 2)} ${meta.target.unit || ''}。` : '确认前不会出现真实目标值。'
    } else if (id === 'update') {
      status = history.length ? 'done' : 'waiting'
      value = snapshot?.current_model_sha ? `${snapshot.current_model_sha.slice(0, 12)}…` : '—'
      detail = history.length ? `已追加 ${history.length} 条历史记录并重训；test 视图保持不变。` : '尚未发生判断更新。'
    }
    return { id, title, code, index: index + 1, status, value, detail, record: pendingRecord || lastHistory }
  })
}

export default function EvidenceTrail({ view, landscape, preview, mode, scanning, onDownload, transition }) {
  const meta = useDataset()
  const [selectedNode, setSelectedNode] = useState('data')
  const [newNode, setNewNode] = useState(null)
  const scroller = useRef(null)
  const drag = useRef(null)
  const previousReveals = useRef(0)
  const nodes = useMemo(() => buildNodes(view, landscape, preview, meta), [view, landscape, preview, meta])
  const snapshot = view?.snapshot
  const audit = view?.audit
  const research = mode === 'research'
  const active = nodes.find(node => node.id === selectedNode) || nodes[0]
  useEffect(() => { setSelectedNode('data') }, [view?.snapshot?.project_id])
  useEffect(() => {
    const count = view?.history?.length || 0
    if (count > previousReveals.current) {
      setNewNode('reveal')
      const timer = window.setTimeout(() => setNewNode(null), 900)
      previousReveals.current = count
      return () => window.clearTimeout(timer)
    }
    previousReveals.current = count
    return undefined
  }, [view?.history?.length])
  function pointerDown(event) {
    if (event.target.closest('button')) return
    drag.current = { x: event.clientX, left: scroller.current?.scrollLeft || 0 }
    scroller.current?.setPointerCapture?.(event.pointerId)
  }
  function pointerMove(event) {
    if (!drag.current || !scroller.current) return
    scroller.current.scrollLeft = drag.current.left - (event.clientX - drag.current.x)
  }
  function pointerUp() { drag.current = null }
  function focusNode(id) {
    setSelectedNode(id)
    window.setTimeout(() => document.querySelector('.nt-trail-detail')?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 30)
  }
  return <section className={`nt-trail ${scanning ? 'is-scanning' : ''}`} id="trail" aria-labelledby="nt-trail-title">
    <header className="nt-section-head">
      <div><span className="nt-kicker">{research ? '核验' : 'C1 / EVIDENCE TRAIL'}</span><h2 id="nt-trail-title">{research ? '证据链' : '预测如何被新证据改变'}</h2>{!research && <p>这条时间轴只读取项目已有记录；不重算、不补写、不修改历史。</p>}</div>
      <div className="nt-trail-actions">{onDownload && <button type="button" className="nt-secondary-button" onClick={onDownload}><Download size={14} /> 导出证据摘要</button>}<span className="nt-scan-status"><ScanLine size={14} /> {scanning ? '只读核验中…' : '只读记录'}</span></div>
    </header>
    <div className="nt-trail-scroller" ref={scroller} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp}>
      <div className="nt-trail-line" aria-hidden="true" />
      <ol className="nt-trail-list">
        {nodes.map(node => <li key={node.id} className={`nt-trail-item is-${node.status} ${newNode === node.id ? 'is-new' : ''}`}>
          <button type="button" className={`nt-trail-node ${selectedNode === node.id ? 'is-selected' : ''}`} onClick={() => setSelectedNode(node.id)} aria-pressed={selectedNode === node.id}>
            <span className="nt-trail-index">{String(node.index).padStart(2, '0')}</span>
            <span className="nt-trail-dot">{node.status === 'done' ? <Check size={13} /> : <CircleDashed size={13} />}</span>
            <span className="nt-trail-copy"><small>{node.code}</small><strong>{node.title}</strong><em>{node.value}</em></span>
          </button>
        </li>)}
      </ol>
    </div>
    <div className="nt-trail-detail" aria-live="polite">
      <div className="nt-trail-detail-head"><span className="nt-kicker">{active.code} / DETAIL</span><strong>{active.title}</strong><span className={`nt-state ${active.status === 'done' ? 'nt-state-known' : 'nt-state-open'}`}>{active.status === 'done' ? '已记录' : '尚无记录'}</span></div>
      <p>{active.detail}</p>
      <div className="nt-trail-facts">
        <span>值</span><strong>{active.value}</strong>
        <span>项目</span><code>{snapshot?.project_id || '—'}</code>
        <span>状态</span><code>{snapshot ? statusLabel(snapshot.status) : '尚未创建'}</code>
        <span>数据 SHA</span><code>{snapshot?.source_canonical_sha256 ? `${snapshot.source_canonical_sha256.slice(0, 24)}…` : '—'}</code>
        <span>切分 SHA</span><code>{snapshot?.split_sha256 ? `${snapshot.split_sha256.slice(0, 24)}…` : landscape?.split_sha256 ? `${landscape.split_sha256.slice(0, 24)}…` : '—'}</code>
        <span>事件链</span><code>{audit?.event_chain_sha256 ? `${audit.event_chain_sha256.slice(0, 24)}…` : '—'}</code>
        {mode === 'research' && <><span>test SHA</span><code>{snapshot?.test_sha256 || '—'}</code><span>模型 SHA</span><code>{snapshot?.current_model_sha || '—'}</code></>}
      </div>
      <p className="nt-trail-boundary"><LockKeyhole size={13} /> 时间戳和字段确认表单不在当前 API 响应中；此处按事件顺序显示，不虚构时间。{!snapshot && ' 创建项目后才会出现候选、封存、揭示和更新记录。'}</p>
      {active.id === 'update' && <StateDiff transition={transition} />}
    </div>
    {!research && <ScienceScenes view={view} preview={preview} pending={view?.pending} last={view?.history?.at(-1)} transition={transition} onFocus={focusNode} />}
    <footer className="nt-trail-foot"><span><GitBranch size={14} /> {snapshot ? `${snapshot.revealed_count} 次揭示 · 剩余预算 ${snapshot.remaining_budget}` : '尚未开始回放'}</span><span><ShieldAlert size={13} /> 历史回放，不是现场新试验</span><button type="button" className="nt-link-button" onClick={() => setSelectedNode(nodes.at(-1).id)}>展开最近的判断 <ArrowRight size={12} /></button></footer>
  </section>
}


function StateDiff({ transition }) {
  if (!transition?.before || !transition?.after) return <div className="nt-state-diff is-unavailable"><span>前后状态对照</span><strong>—</strong><p>当前 API 没有可用的前后模型记录；不补造。</p></div>
  const rows = [
    ['model SHA', transition.before.model_sha, transition.after.model_sha],
    ['revealed count', transition.before.revealed_count, transition.after.revealed_count],
    ['remaining budget', transition.before.remaining_budget, transition.after.remaining_budget],
    ['observed / candidate', `${transition.before.observed_count} / ${transition.before.candidate_count}`, `${transition.after.observed_count} / ${transition.after.candidate_count}`],
    ['pending / latest row', transition.before.pending_row, transition.after.latest_revealed_row],
  ]
  return <div className="nt-state-diff"><div className="nt-diff-head"><span>前后状态对照 / STATE DIFF</span><span>揭示前 → 揭示后</span></div><div className="nt-diff-rows">{rows.map(([label, before, after]) => <div key={label}><span>{label}</span><code title={String(before)}>{before ? `${String(before).slice(0, 18)}${String(before).length > 18 ? '…' : ''}` : '—'}</code><b>→</b><code title={String(after)}>{after ? `${String(after).slice(0, 18)}${String(after).length > 18 ? '…' : ''}` : '—'}</code></div>)}</div></div>
}
