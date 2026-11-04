import React, { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Download, Gauge, GitCompareArrows, Play, RefreshCw, RotateCcw, ShieldCheck, Table2, X } from 'lucide-react'
import { number } from './data'
import { useDataset } from './dataset'

const STRATEGY_LABEL = { random: '随机对照', greedy_prediction: '预测优先', max_disagreement: '最大差异' }
const STRATEGY_COLOR = { random: '#5d7f9d', greedy_prediction: '#2d8b7e', max_disagreement: '#a87532' }
const METRIC = {
  gap: { label: '剩余差距', copy: '方案全集事后最优 − 当前最好实测；越低越好。', key: 'gap' },
  best: { label: '发现轨迹', copy: '已公布方案中的最好实测值；方向随目标。', key: 'best_target' },
  error: { label: '预测误差', copy: '该轮保存预测与公布实测的绝对误差；越低越好。', key: 'prediction_error' },
}
const SEEDS = [20261026, 20261027, 20261028, 20261029, 20261030, 20261031, 20261032, 20261033, 20261034, 20261035]
const STATUS_LABEL = { completed: 'complete', stopped_threshold: 'threshold stopped', candidate_exhausted: 'candidate exhausted', timeout: 'stopped by time limit', failed: 'failed', not_run: 'not run', planned: 'planned', running: 'running', complete: 'complete', incomplete: 'incomplete' }

async function api(path, method = 'GET', body) {
  const response = await fetch(path, { method, cache: 'no-store', headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    const error = new Error(typeof detail === 'string' ? detail : (detail?.message || `请求失败（${response.status}）`))
    error.data = detail
    throw error
  }
  return data
}

function rid() { return `req_${(crypto.randomUUID?.() || `${Date.now()}${Math.random()}`).replaceAll('-', '').slice(0, 32)}` }

function metricValue(cell, mode) {
  return (cell.rounds || []).map(row => ({ round: row.round, value: mode === 'gap' ? row.oracle_gap : mode === 'best' ? row.best_revealed_target : row.absolute_error }))
}

function linePath(points, width, height, bounds) {
  if (!points.length) return ''
  return points.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ')
}

function Interferometer({ comparison, metric, lens, setLens, reduced, research }) {
  const summary = comparison.summary
  const plan = comparison.plan
  const cells = comparison.ledger.cells
  const budget = plan.budget
  const width = 900
  const height = 300
  const pad = { left: 48, right: 16, top: 20, bottom: 30 }
  const rounds = Array.from({ length: budget }, (_, i) => i + 1)
  const values = []
  for (const cell of cells) for (const row of metricValue(cell, metric)) if (Number.isFinite(row.value)) values.push(row.value)
  for (const strategy of plan.strategies) for (const r of rounds) {
    const stats = summary.strategies[strategy]?.rounds?.[String(r)]?.[METRIC[metric].key]
    if (stats) [stats.q1, stats.q3, stats.median].forEach(v => { if (Number.isFinite(v)) values.push(v) })
  }
  let lo = Math.min(...values), hi = Math.max(...values)
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) { lo = 0; hi = 1 }
  if (hi - lo < 1e-9) { hi += 1; lo -= 1 }
  const padY = (hi - lo) * 0.1
  lo = Math.max(0, lo - padY); hi += padY
  const x = r => pad.left + (budget <= 1 ? 0 : (r - 1) / (budget - 1)) * (width - pad.left - pad.right)
  const y = v => pad.top + (1 - (v - lo) / (hi - lo)) * (height - pad.top - pad.bottom)
  const lensX = x(lens)
  return <section className="nt-interferometer" aria-labelledby="nt-interferometer-title">
    <header className="nt-ob-section-head"><div><span className="nt-kicker">STRATEGY INTERFEROMETER / 策略干涉仪</span><h2 id="nt-interferometer-title">{research ? '策略轨迹' : '同一预算下，三条航迹如何分开？'}</h2><p>{research ? `${METRIC[metric].label} · seed / median / IQR` : `${METRIC[metric].copy} 每个 seed 是一条低饱和实验丝线；粗线是 median，压痕带是 IQR，不是 95% CI。`}</p></div><div className="nt-chart-caption"><span>当前读法：{METRIC[metric].label}</span><small>切换读法在图表上方</small></div></header>
    <div className="nt-chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} className="nt-interferometer-chart" role="img" aria-label={`三策略${METRIC[metric].label}轨迹；横轴为 reveal 轮次`}>
        {[0, .25, .5, .75, 1].map(t => <g key={t}><line x1={pad.left} x2={width - pad.right} y1={pad.top + t * (height - pad.top - pad.bottom)} y2={pad.top + t * (height - pad.top - pad.bottom)} className="nt-chart-grid" /><text x={4} y={pad.top + t * (height - pad.top - pad.bottom) + 3} className="nt-chart-tick">{number(hi - t * (hi - lo), 2)}</text></g>)}
        {plan.strategies.map(strategy => <g key={strategy}>
          {cells.filter(cell => cell.strategy === strategy).map(cell => {
            const points = metricValue(cell, metric).filter(row => Number.isFinite(row.value)).map(row => ({ x: x(row.round), y: y(row.value) }))
            return <g key={`${cell.seed}-${strategy}`}><path d={linePath(points, width, height, { lo, hi })} className={`nt-seed-line ${reduced ? 'is-reduced' : ''}`} stroke={STRATEGY_COLOR[strategy]} />{points.filter(point => Number.isFinite(point.x) && Number.isFinite(point.y)).map((point, index) => <circle key={index} cx={point.x} cy={point.y} r="1.6" fill={STRATEGY_COLOR[strategy]} opacity=".35" />)}</g>
          })}
        </g>)}
        {plan.strategies.map(strategy => {
          const median = rounds.map(r => summary.strategies[strategy]?.rounds?.[String(r)]?.[METRIC[metric].key]?.median).map((v, i) => ({ x: x(i + 1), y: Number.isFinite(v) ? y(v) : null })).filter(p => p.y != null)
          const q1 = rounds.map(r => summary.strategies[strategy]?.rounds?.[String(r)]?.[METRIC[metric].key]?.q1)
          const q3 = rounds.map(r => summary.strategies[strategy]?.rounds?.[String(r)]?.[METRIC[metric].key]?.q3)
          const band = [...q1.map((v, i) => Number.isFinite(v) ? `${i ? 'L' : 'M'} ${x(i + 1)} ${y(v)}` : ''), ...[...q3].reverse().map((v, i) => Number.isFinite(v) ? `L ${x(budget - i)} ${y(v)}` : ''), 'Z'].join(' ')
          return <g key={`median-${strategy}`}><path d={band} fill={STRATEGY_COLOR[strategy]} className="nt-iqr-band" /><path d={linePath(median)} fill="none" stroke={STRATEGY_COLOR[strategy]} className="nt-median-line" />{median.filter(point => Number.isFinite(point.x) && Number.isFinite(point.y)).map((point, index) => <circle key={index} cx={point.x} cy={point.y} r="2.8" fill="#f8f6ee" stroke={STRATEGY_COLOR[strategy]} strokeWidth="2" />)}</g>
        })}
        <line x1={lensX} x2={lensX} y1={pad.top} y2={height - pad.bottom} className="nt-budget-cursor" />
        <circle cx={lensX} cy={pad.top} r="4" className="nt-budget-knob" />
        {rounds.map(r => <text key={r} x={x(r)} y={height - 8} textAnchor="middle" className="nt-chart-tick">{r}</text>)}
      </svg>
      <div className="nt-budget-lens">
        <label htmlFor="nt-budget-lens"><Gauge size={14} /> BUDGET LENS <strong>round {lens}</strong></label>
        <input id="nt-budget-lens" type="range" min="1" max={budget} step="1" value={lens} onChange={e => setLens(Number(e.target.value))} />
        <div className="nt-budget-lens-foot"><span>round 1</span><span>只改变视图，不写记录</span><span>round {budget}</span></div>
      </div>
    </div>
    <div className="nt-chart-legend">{plan.strategies.map(strategy => <span key={strategy}><i style={{ background: STRATEGY_COLOR[strategy] }} />{STRATEGY_LABEL[strategy]}<small>seed 线 · median · IQR 带</small></span>)}</div>
  </section>
}

function FairnessRail({ plan, dataset }) {
  const items = [
    ['同一数据包', dataset?.display_name || plan?.dataset_display_name, `input ${plan?.dataset_passport_ref?.sha256?.input || '—'}`],
    ['同一起点', `${plan?.dataset_passport_ref?.counts?.train ?? '—'} observed · ${plan?.dataset_passport_ref?.counts?.candidate ?? '—'} candidates`, `split ${plan?.dataset_passport_ref?.sha256?.split || '—'}`],
    ['同一预算', `${plan?.budget ?? '—'} reveals / cell`, `${plan?.strategies?.length || 3} strategies fixed`],
    ['固定 seeds', plan ? `${plan.seeds.length} seeds · ${plan.exploratory_preview ? 'Quick Rehearsal' : 'Evidence Run'}` : 'preview required', plan ? `plan ${plan.plan_sha256?.slice(0, 16) || '—'}…；10 个种子观察算法随机性，不是 10 次独立物理实验` : 'no frozen plan'],
  ]
  return <section className="nt-fairness-rail" aria-label="公平比较协议"><div className="nt-fairness-title">FAIRNESS RAIL <small>same data · same start · same budget · fixed seeds</small></div><div className="nt-fairness-bolts">{items.map(([title, value, detail], i) => <div className="nt-fairness-bolt" key={title} tabIndex="0"><span className="nt-bolt-index">{String(i + 1).padStart(2, '0')}</span><strong>{title}</strong><span>{value}</span><details><summary>查看协议</summary><code>{detail}</code></details></div>)}</div></section>
}

function PairedPlate({ summary, plan, lens, research }) {
  return <section className="nt-paired-plate"><header><div><span className="nt-kicker">PAIRED EVIDENCE PLATE / 并列证据</span><h2>{research ? '当前轮比较' : '同一轮次，三种策略各自的分布'}</h2></div><span className="nt-round-caption">BUDGET LENS · ROUND {lens}</span></header><div className="nt-paired-table" role="table" aria-label="三策略当前轮证据"><div className="nt-paired-row nt-paired-head" role="row"><span>策略</span><span>median oracle gap</span><span>IQR</span><span>有效 / 计划</span><span>threshold</span></div>{plan.strategies.map(strategy => { const stats = summary.strategies[strategy]; const roundStats = stats?.rounds?.[String(lens)] || {}; const round = roundStats.gap || {}; const th = stats?.threshold; return <div className="nt-paired-row" role="row" key={strategy}><span className="nt-strategy-name"><i style={{ background: STRATEGY_COLOR[strategy] }} />{STRATEGY_LABEL[strategy]}<code>{strategy}</code></span><strong>{round.median == null ? '—' : number(round.median, 3)} {plan.target.unit || ''}</strong><span>{round.iqr == null ? '—' : number(round.iqr, 3)}</span><span>{roundStats.n ?? 0} / {roundStats.planned ?? plan.seeds.length}</span><span>{th ? `${th.success_count} / ${th.planned_denominator}` : 'not configured'}</span></div> })}</div>{!research && <p className="nt-note">IQR 是四分位距，不是 95% 置信区间；有效分母不足时不出结论。</p>}</section>
}

function RunMatrix({ comparison, onCell, research }) {
  const plan = comparison.plan
  const byKey = new Map(comparison.ledger.cells.map(cell => [`${cell.seed}:${cell.strategy}`, cell]))
  return <section className="nt-run-matrix"><header className="nt-ob-section-head"><div><span className="nt-kicker">RUN MATRIX / 10 × 3</span><h2>{research ? '运行矩阵' : '每个 seed × strategy 都有独立账本'}</h2><p>{research ? '逐轮保存 / 公布 / 更新' : '点击单元格查看逐轮 prediction seal → reveal → update；不提供重跑单格。'}</p></div><Table2 size={21} /></header><div className="nt-matrix" role="grid" aria-label="seed 与策略状态矩阵"><div className="nt-matrix-head" role="row"><span>SEED</span>{plan.strategies.map(s => <span key={s}>{STRATEGY_LABEL[s]}<code>{s}</code></span>)}</div>{plan.seeds.map(seed => <div className="nt-matrix-row" role="row" key={seed}><code>{seed}</code>{plan.strategies.map(strategy => { const cell = byKey.get(`${seed}:${strategy}`); return <button type="button" role="gridcell" key={strategy} className={`nt-matrix-cell is-${cell?.status || 'not_run'}`} onClick={() => onCell(cell || { seed, strategy, status: 'not_run', rounds: [] })} title={`${seed} / ${strategy} / ${STATUS_LABEL[cell?.status || 'not_run']}`}><span>{STATUS_LABEL[cell?.status || 'not_run']}</span><small>{cell?.rounds?.length ?? 0} rounds</small></button> })}</div>)}</div></section>
}

function CellSlice({ cell, plan, onClose }) {
  if (!cell) return null
  return <aside className="nt-cell-slice" role="dialog" aria-modal="false" aria-label="只读轨迹切片"><header><div><span className="nt-kicker">READ-ONLY TRACE SLICE</span><strong>{cell.seed} · {STRATEGY_LABEL[cell.strategy]}</strong></div><button type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭轨迹切片"><X size={14} /></button></header><div className="nt-cell-slice-status">{STATUS_LABEL[cell.status] || cell.status} · {cell.rounds?.length || 0} rounds</div>{cell.rounds?.length ? <ol>{cell.rounds.map(row => <li key={row.round}><span>R{row.round}</span><code>{row.row_id}</code><b>{number(row.prediction, 3)}</b><span>→ {number(row.revealed_target, 3)} {plan.target.unit || ''}</span><small>error {number(row.absolute_error, 3)} · best {number(row.best_revealed_target, 3)} · gap {number(row.oracle_gap, 3)}</small></li>)}</ol> : <p className="nt-note">没有已公布轮次；不把 not run 或 failed 填成 0。</p>}</aside>
}

function ResearchGrid({ comparison }) {
  const { plan, summary, audit, manifest } = comparison
  return <section className="nt-research-grid"><div className="nt-research-block"><span className="nt-kicker">EVALUATION PLAN</span><dl><dt>plan SHA</dt><dd><code>{plan.plan_sha256}</code></dd><dt>metrics</dt><dd>{summary.metrics_version}</dd><dt>mode</dt><dd>{plan.comparison_mode} · eligible {String(plan.eligible_for_comparison_claim)}</dd><dt>seeds</dt><dd>{plan.seeds.join(' · ')}</dd><dt>strategies</dt><dd>{plan.strategies.join(' · ')}</dd><dt>audit</dt><dd>{audit?.valid ? 'valid' : 'invalid'} · tree {comparison.tree_sha256?.slice(0, 16)}…</dd><dt>auditor</dt><dd>{audit?.audit_schema || '—'} · {audit?.auditor_version || '—'} · semantic_replay {String(audit?.semantic_replay)}</dd><dt>seed 解读</dt><dd>{comparison.seed_interpretation || audit?.seed_interpretation || '10 个种子用于观察算法随机性，不是 10 次独立物理实验。'}</dd><dt>manifest</dt><dd><code>{manifest.comparison_id}</code></dd></dl>{audit?.errors?.length ? <div className="nt-audit-errors">{audit.errors.slice(0, 4).map((e, i) => <p key={i}>{e}</p>)}</div> : null}</div><div className="nt-research-block"><span className="nt-kicker">SEED-LEVEL TERMINAL ROWS</span><div className="nt-seed-table"><div className="nt-seed-row nt-seed-head"><span>seed</span><span>strategy</span><span>status</span><span>rounds</span><span>oracle gap</span><span>best</span></div>{plan.seeds.flatMap(seed => plan.strategies.map(strategy => { const cell = summary.strategies[strategy]?.cells?.find(c => c.seed === seed); return <div className="nt-seed-row" key={`${seed}-${strategy}`}><code>{seed}</code><span>{strategy}</span><span>{STATUS_LABEL[cell?.status] || 'not run'}</span><span>{cell?.rounds_used ?? '—'}</span><span>{cell?.terminal_oracle_gap == null ? '—' : number(cell.terminal_oracle_gap, 3)}</span><span>{cell?.terminal_best_target == null ? '—' : number(cell.terminal_best_target, 3)}</span></div> }))}</div></div><div className="nt-research-block"><span className="nt-kicker">PAIRED DIFFERENCES · comparator − random</span><table className="nt-pair-table"><thead><tr><th>seed</th><th>comparator</th><th>gap − random gap</th></tr></thead><tbody>{Object.entries(summary.paired).flatMap(([strategy, value]) => value.rows.map(row => <tr key={`${strategy}-${row.seed}`}><td>{row.seed}</td><td>{strategy}</td><td>{number(row.difference, 3)}</td></tr>))}</tbody></table><p className="nt-note">负值表示 comparator 的终轮方案差距更小；这只是当前冻结数据包与协议下的描述性配对差异。</p></div><div className="nt-research-block"><span className="nt-kicker">EXPORT / READ-ONLY</span><p>导出 ledger 与 summary；不包含未公布 candidate 或 independent test 逐条标签。</p><ExportButtons comparisonId={comparison.manifest.comparison_id} /></div></section>
}

async function downloadExport(id, fmt) {
  const data = await api(`/api/comparisons/${id}/export?format=${fmt}`)
  const content = fmt === 'csv' ? data.content : JSON.stringify(data, null, 2)
  const blob = new Blob([content], { type: fmt === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `NextTest_${id}.${fmt}`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function ExportButtons({ comparisonId }) { return <div className="nt-export-buttons"><button type="button" className="nt-secondary-button" onClick={() => downloadExport(comparisonId, 'json')}><Download size={13} /> JSON</button><button type="button" className="nt-secondary-button" onClick={() => downloadExport(comparisonId, 'csv')}><Download size={13} /> CSV</button></div> }

export default function StrategyObservatory({ open, datasetId, onClose, onPassport, mode = 'explore', onMode }) {
  const meta = useDataset()
  const [evidenceMode, setEvidenceMode] = useState('evidence')
  const [goal, setGoal] = useState('maximize')
  const [threshold, setThreshold] = useState('')
  const [budget, setBudget] = useState(2)
  const [preview, setPreview] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [metric, setMetric] = useState('gap')
  const [lens, setLens] = useState(1)
  const [cell, setCell] = useState(null)
  const [reduced, setReduced] = useState(false)
  const [runState, setRunState] = useState('')
  const lastRun = useRef(false)

  const datasetKey = datasetId || 'demo-concrete'
  useEffect(() => { if (open) { const mq = matchMedia('(prefers-reduced-motion: reduce)'); setReduced(mq.matches); const fn = e => setReduced(e.matches); mq.addEventListener?.('change', fn); return () => mq.removeEventListener?.('change', fn) } }, [open])
  useEffect(() => {
    if (!open || comparison) return
    let cancelled = false
    const timer = setTimeout(() => {
      api('/api/comparisons/preview', 'POST', { dataset_id: datasetKey, goal, threshold: threshold === '' ? null : Number(threshold), budget, mode: evidenceMode }).then(data => { if (!cancelled) setPreview(data) }).catch(err => { if (!cancelled) setError(err.message) })
    }, 180)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [open, datasetKey, goal, threshold, budget, evidenceMode, comparison])
  useEffect(() => {
    if (!open) return
    const id = localStorage.getItem('nexttest.comparison')
    if (!id) return
    api(`/api/comparisons/${id}`).then(value => { setComparison(value); setLens(value.plan.budget); localStorage.setItem('nexttest.comparison', value.manifest.comparison_id) }).catch(() => {})
  }, [open])
  useEffect(() => { if (comparison?.plan) setLens(value => Math.min(Math.max(1, value || 1), comparison.plan.budget)) }, [comparison?.plan?.budget])

  const plan = comparison?.plan || preview?.plan_preview
  const summary = comparison?.summary
  const audit = comparison?.audit
  const scale = preview?.calculation_scale
  const complete = summary?.complete && audit?.valid && Boolean(summary?.eligible_for_comparison_claim)
  const canRun = !busy && preview && !comparison

  async function start() {
    setBusy(true); setError(''); setRunState('正在冻结 evaluation plan…')
    try {
      const created = await api('/api/comparisons', 'POST', { dataset_id: datasetKey, goal, threshold: threshold === '' ? null : Number(threshold), budget, mode: evidenceMode, request_id: rid() })
      setComparison(created); localStorage.setItem('nexttest.comparison', created.manifest.comparison_id)
      setRunState('计划已冻结。确认协议后开始串行回放。')
    } catch (err) { setError(err.message); setRunState('') } finally { setBusy(false) }
  }

  async function resume() {
    const id = localStorage.getItem('nexttest.comparison'); if (!id) return
    setBusy(true); setError('')
    try { const value = await api(`/api/comparisons/${id}`); setComparison(value); setLens(value.plan?.budget || 1) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  function resetView() { setComparison(null); setPreview(null); setCell(null); setError(''); setRunState(''); localStorage.removeItem('nexttest.comparison') }
  const currentRound = plan?.budget ? lens : 1

  if (!open) return null
  return <div className="nt-observatory-layer" role="dialog" aria-modal="true" aria-labelledby="nt-observatory-title">
    <div className={`nt-observatory ${mode === 'research' ? 'is-research' : 'is-explore'}`}>
      <header className="nt-ob-header"><div className="nt-ob-title"><button type="button" className="nt-back-button" onClick={onClose}><ArrowLeft size={14} /> 返回单项目工作台</button><span className="nt-kicker">STRATEGY OBSERVATORY / 策略观测台</span><h1 id="nt-observatory-title">{mode === 'research' ? '策略实验' : <>同一数据、同一起点、同一预算，<em>三种策略会把机会带到哪里？</em></>}</h1><p>{mode === 'research' ? '冻结协议 · 历史回放' : '历史标签回放 · 非新物理实验 · 非确认性比较 · 不是排行榜'}</p></div><div className="nt-ob-identity"><button type="button" className="nt-ob-dataset" onClick={onPassport}><span className="nt-kicker">DATASET PASSPORT</span><strong>{plan?.dataset_display_name || meta.displayName}</strong><small>{plan?.dataset_short_id || meta.shortId || 'demo'} · {plan?.target?.display_name || meta.target.displayName} · {plan?.target?.unit || meta.target.unit || 'unit not supplied'}</small></button><div className="nt-ob-mode"><button type="button" className={mode === 'explore' ? 'is-active' : ''} onClick={() => onMode?.('explore')}>Explore</button><button type="button" className={mode === 'research' ? 'is-active' : ''} onClick={() => onMode?.('research')}>Research</button></div><button type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭策略观测台"><X size={15} /></button></div></header>

      <div className="nt-ob-boundary"><ShieldCheck size={13} /> {mode === 'research' ? '冻结回放 · 失败与未运行不填 0' : '当前视图只描述冻结数据包上的历史回放；失败、未运行与方案耗尽不填 0，不从分母消失。'}<span>3 × {plan?.seeds?.length || (evidenceMode === 'evidence' ? 10 : 3)} × {plan?.budget || budget} = 最多 {3 * (plan?.seeds?.length || (evidenceMode === 'evidence' ? 10 : 3)) * (plan?.budget || budget)} 次历史公布 / 模型更新</span></div>

      {error && <div className="nt-ob-error" role="alert">{error}</div>}
      {runState && <div className="nt-ob-running" role="status"><RefreshCw size={14} /> {runState}</div>}

      {!comparison && <section className="nt-foundry"><div className="nt-foundry-main"><span className="nt-kicker">RUN FOUNDRY / 运行铸造</span><h2>{mode === 'research' ? '比较计划' : '先冻结协议，再让历史回放发生。'}</h2><p>{mode === 'research' ? '同包 · 同切分 · 同预算' : '三种策略由同一包、同一 split、同一初始 pool、同一模型 seed、同一 goal/threshold/budget 驱动。设置只在冻结前生效。'}</p><div className="nt-foundry-controls"><div><span>01 / goal</span><div className="nt-segmented">{['maximize', 'minimize'].map(g => <button key={g} type="button" className={goal === g ? 'is-active' : ''} onClick={() => setGoal(g)}>{g === 'maximize' ? '最大化' : '最小化'}</button>)}</div></div><div><span>02 / threshold · optional</span><input type="number" step="0.01" value={threshold} onChange={e => setThreshold(e.target.value)} placeholder="未设置" aria-label="threshold 可选" /></div><div><span>03 / budget · 1..10</span><input type="range" min="1" max="10" step="1" value={budget} onChange={e => setBudget(Number(e.target.value))} aria-label="每 cell 的 reveal 预算" /><strong>{budget} reveals / cell</strong></div><div><span>04 / run mode</span><div className="nt-segmented"><button type="button" className={evidenceMode === 'evidence' ? 'is-active' : ''} onClick={() => { setEvidenceMode('evidence'); setBudget(Math.min(budget, 10)) }}>Evidence Run · 10 fixed seeds</button><button type="button" className={evidenceMode === 'rehearsal' ? 'is-active' : ''} onClick={() => { setEvidenceMode('rehearsal'); setBudget(Math.min(budget, 3)) }}>Quick Rehearsal · 3 seeds</button></div><small>{evidenceMode === 'rehearsal' ? 'exploratory_preview=true · eligible_for_comparison_claim=false' : 'fixed seeds · eligible_for_comparison_claim=true'}</small></div></div><div className="nt-foundry-scale">{scale ? <><strong>{scale.strategies} × {scale.seeds} × {scale.budget} = {scale.max_reveals}</strong><span>最多历史公布 / 模型更新次数；不是新实验数量</span></> : <><RefreshCw size={13} /> 正在预览公平比较协议…</>}</div><button type="button" className="nt-primary nt-run-button" disabled={!canRun || (evidenceMode === 'rehearsal' && plan?.eligible_for_comparison_claim)} onClick={start}><Play size={15} /> 冻结比较计划并开始历史回放</button></div><aside className="nt-foundry-preview"><span className="nt-kicker">PROTOCOL PREVIEW</span>{plan ? <dl><dt>dataset</dt><dd>{plan.dataset_display_name}</dd><dt>target</dt><dd>{plan.target.display_name} · {plan.target.unit || 'unit not supplied'}</dd><dt>goal</dt><dd>{plan.goal} · threshold {plan.threshold ?? '—'}</dd><dt>strategies</dt><dd>{plan.strategies.join(' · ')}</dd><dt>seeds</dt><dd>{plan.seeds.join(' · ')}</dd><dt>fairness</dt><dd>same split / initial pool / model seed / budget</dd><dt>plan SHA</dt><dd><code>{plan.plan_sha256?.slice(0, 24) || 'will freeze'}…</code></dd></dl> : <p className="nt-note">预览尚未就绪。</p>}<div className="nt-foundry-note">模型：RandomForestRegressor n_estimators=120 · max_depth=8 · min_samples_leaf=2 · n_jobs=1。选择公式和 tie-break 沿用 P1–P3，不新增策略。</div></aside></section>}

      {comparison && <>
        <FairnessRail plan={comparison.plan} dataset={comparison.dataset} />
        <div className="nt-ob-statusbar"><span className={`nt-ob-status is-${comparison.state.status}`}>{comparison.state.status}</span><span>plan frozen · {comparison.plan.comparison_mode}</span><span>{comparison.summary ? `${comparison.summary.observed_cells} / ${comparison.summary.planned_cells} cells` : 'awaiting run'}</span><span>{comparison.audit?.valid ? 'audit valid' : 'audit unavailable / invalid'}</span><button type="button" className="nt-link-button" onClick={resetView}><RotateCcw size={12} /> 新的比较</button><button type="button" className="nt-link-button" onClick={resume}><RefreshCw size={12} /> 只读恢复</button></div>
        {comparison.state.status === 'planned' && <div className="nt-ob-callout"><strong>计划已冻结，尚未运行。</strong><span>evaluation_plan.json 已独占落盘；运行会从第一个计划单元串行开始，已完成单元不会重跑。</span><button type="button" className="nt-primary" disabled={busy} onClick={async () => { setBusy(true); setError(''); setRunState('计划已冻结；开始串行历史回放…'); try { const value = await api(`/api/comparisons/${comparison.manifest.comparison_id}/run`, 'POST', { request_id: rid() }); setComparison(value); setLens(value.plan.budget); setRunState('') } catch (err) { setError(err.message); setRunState('') } finally { setBusy(false) } }}><Play size={14} /> 开始串行回放</button></div>}
        {summary && <>
          <div className="nt-metric-tabs" role="tablist" aria-label="轨迹读法">{Object.entries(METRIC).map(([key, item]) => <button key={key} type="button" role="tab" aria-selected={metric === key} className={metric === key ? 'is-active' : ''} onClick={() => setMetric(key)}>{item.label}</button>)}</div>
          <Interferometer comparison={comparison} metric={metric} lens={currentRound} setLens={setLens} reduced={reduced} research={mode === 'research'} />
          <PairedPlate summary={summary} plan={comparison.plan} lens={currentRound} research={mode === 'research'} />
          <section className={`nt-conclusion ${complete ? 'is-complete' : 'is-incomplete'}`}><span className="nt-kicker">PLAIN-LANGUAGE CONCLUSION / 普通话结论</span><p>{summary.conclusion}</p><small>{complete ? `有效计划单元 ${summary.observed_cells} / ${summary.planned_cells}；10 个种子用于观察算法随机性，不是 10 次独立物理实验；IQR 不是 95% CI；没有显著性检验。` : '不完整运行不生成优胜结论；所有状态仍保留在 Run Matrix。10 个种子用于观察算法随机性，不是 10 次独立物理实验。'}</small></section>
          <RunMatrix comparison={comparison} onCell={setCell} research={mode === 'research'} />
          {mode === 'research' && <ResearchGrid comparison={comparison} />}
          {cell && <CellSlice cell={cell} plan={comparison.plan} onClose={() => setCell(null)} />}
        </>}
      </>}

      <footer className="nt-ob-footer"><span>NextTest · Strategy Observatory · historical replay</span><span>策略公式 / split / RandomForest 参数未改变 · 不上传网络</span></footer>
    </div>
  </div>
}
