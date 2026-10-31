import React, { useEffect, useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, Columns2, Grid2X2, List, Radar, ShieldAlert } from 'lucide-react'
import { candidateState, controlEntries, number, strategyLabel } from './data'
import { useDataset, labelFor, unitFor } from './dataset'
import StrategyLens from './StrategyLens'

const W = 720
const H = 380
const PAD = { left: 50, right: 20, top: 26, bottom: 42 }

function extent(rows, key) {
  const values = rows.map(row => Number(row[key] ?? row.controls?.[key])).filter(Number.isFinite)
  return values.length ? [Math.min(...values), Math.max(...values)] : [0, 1]
}
function toX(value, low, high) { return PAD.left + (value - low) / Math.max(high - low, .0001) * (W - PAD.left - PAD.right) }
function toY(value, low, high) { return H - PAD.bottom - (value - low) / Math.max(high - low, .0001) * (H - PAD.top - PAD.bottom) }

export default function PossibilityAtlas({ observedRows = [], candidates = [], selectedId, compareIds = [], onSelect, onCompare, viewMode, onViewMode, view, mode, hideAside = false, loading = false, strategy, onStrategy, preview }) {
  const meta = useDataset()
  const [xKey, setXKey] = useState(meta.features[0]?.key || 'x')
  const [yKey, setYKey] = useState(meta.features[1]?.key || 'y')
  useEffect(() => {
    if (!meta.features.some(item => item.key === xKey)) setXKey(meta.features[0]?.key || 'x')
    if (!meta.features.some(item => item.key === yKey)) setYKey(meta.features[1]?.key || 'y')
  }, [meta.features])
  const [hover, setHover] = useState(null)
  const combined = [...observedRows, ...candidates.map(row => ({ ...row, ...row.controls }))]
  const [xMin, xMax] = extent(combined, xKey).length ? extent(combined, xKey) : [0, 1]
  const [yMin, yMax] = extent(combined, yKey).length ? extent(combined, yKey) : [0, 1]
  const selected = candidates.find(row => row.row_id === selectedId)
  const compare = candidates.find(row => compareIds.includes(row.row_id) && row.row_id !== selectedId)
  const tableRows = useMemo(() => candidates, [candidates])
  const focusRow = (event, index) => {
    if (!['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) return
    event.preventDefault()
    if (event.key === 'Enter' || event.key === ' ') { onSelect(tableRows[index].row_id); return }
    const next = tableRows[(index + (event.key === 'ArrowDown' ? 1 : -1) + tableRows.length) % tableRows.length]
    if (next) {
      onSelect(next.row_id)
      document.getElementById(`nt-candidate-${next.row_id}`)?.focus()
    }
  }
  return <section className="nt-atlas" id="atlas" aria-labelledby="nt-atlas-title">
    <header className="nt-section-head">
      <div><span className="nt-kicker">A2 / POSSIBILITY ATLAS</span><h2 id="nt-atlas-title">{mode === 'research' ? '候选' : '未知不在空白里，而在选择里'}</h2>{mode !== 'research' && <p>同一组候选事实，两种读法：航图看结构，表格读精确数值。选择在这两处保持同步。</p>}</div>
      <div className="nt-segmented" role="group" aria-label="航图或表格">
        <button type="button" className={viewMode === 'atlas' ? 'is-selected' : ''} onClick={() => onViewMode('atlas')}><Radar size={14} /> 航图</button>
        <button type="button" className={viewMode === 'table' ? 'is-selected' : ''} onClick={() => onViewMode('table')}><List size={14} /> 表格</button>
      </div>
    </header>
    <StrategyLens strategy={strategy} view={view} preview={preview} pending={view?.pending} mode={mode} onStrategy={onStrategy} />
    <div className="nt-atlas-grid">
      <div className="nt-atlas-panel">
        <div className="nt-axis-controls">
          <label>横轴<select value={xKey} onChange={e => setXKey(e.target.value)}>{meta.features.map(item => <option key={item.key} value={item.key}>{item.displayName} / {item.key}</option>)}</select></label>
          <label>纵轴<select value={yKey} onChange={e => setYKey(e.target.value)}>{meta.features.map(item => <option key={item.key} value={item.key}>{item.displayName} / {item.key}</option>)}</select></label>
          <span className="nt-plot-count">{candidates.length} 个未揭示候选 · {observedRows.length} 个已观测</span>
        </div>
        {viewMode === 'table' ? <CandidateTable rows={tableRows} selectedId={selectedId} compareIds={compareIds} onSelect={onSelect} onCompare={onCompare} mode={mode} view={view} onFocusRow={focusRow} /> :
          <div className="nt-atlas-plot">
            {loading && !candidates.length && <div className="nt-atlas-loading"><span className="nt-scan-line" /> 正在读取未揭示候选投影…</div>}
            {!loading && !candidates.length && <div className="nt-unavailable"><ShieldAlert size={16} /> 候选投影不可用：后端没有返回候选数据，不生成示例点。</div>}
            {candidates.length > 0 && <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`候选与已观测记录的${labelFor(meta, xKey)}对${labelFor(meta, yKey)}投影`}>
              <defs>
                <pattern id="nt-atlas-grid" width="45" height="38" patternUnits="userSpaceOnUse"><path d="M45 0H0V38" fill="none" stroke="rgba(83,227,194,.1)" /></pattern>
                <radialGradient id="nt-atlas-depth" cx="56%" cy="34%" r="78%"><stop offset="0%" stopColor="#1b6070" stopOpacity=".48" /><stop offset="54%" stopColor="#0d2635" stopOpacity=".35" /><stop offset="100%" stopColor="#06131d" stopOpacity=".9" /></radialGradient>
                <filter id="nt-atlas-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
              </defs>
              <rect x={PAD.left} y={PAD.top} width={W - PAD.left - PAD.right} height={H - PAD.top - PAD.bottom} fill="url(#nt-atlas-depth)" />
              <rect x={PAD.left} y={PAD.top} width={W - PAD.left - PAD.right} height={H - PAD.top - PAD.bottom} fill="url(#nt-atlas-grid)" />
              <path d={`M${PAD.left} ${PAD.top}V${H - PAD.bottom}H${W - PAD.right}`} className="nt-axis-line" />
              {observedRows.map(row => <circle key={row._row_id} cx={toX(Number(row[xKey]), xMin, xMax)} cy={toY(Number(row[yKey]), yMin, yMax)} r="2.2" className="nt-atlas-known" />)}
              {candidates.map(row => {
                const active = row.row_id === selectedId; const compared = compareIds.includes(row.row_id)
                return <g key={row.row_id} tabIndex={0} role="button" aria-label={`候选 ${row.row_id}，预测 ${number(row.prediction, 1)} ${meta.target.unit || ''}`}
                  className={`nt-atlas-candidate ${active ? 'is-selected' : ''} ${compared ? 'is-compared' : ''}`}
                  transform={`translate(${toX(Number(row.controls[xKey]), xMin, xMax)} ${toY(Number(row.controls[yKey]), yMin, yMax)})`}
                  onClick={() => onSelect(row.row_id)} onMouseEnter={() => setHover(row.row_id)} onMouseLeave={() => setHover(null)}
                  onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(row.row_id) } }}>
                  {(active || row.row_id === hover) && <circle className="nt-atlas-aura" r={active ? 18 : 13} />}
                  <circle r={active ? 9 : 5.4} filter={active ? 'url(#nt-atlas-glow)' : undefined} /><circle className="nt-atlas-hit" r="15" />
                  <title>{row.row_id} · 预测 {number(row.prediction, 2)} {meta.target.unit || ''} · 分歧 {number(row.disagreement, 2)}</title>
                </g>
              })}
              {hover && (() => { const row = candidates.find(item => item.row_id === hover); return row ? <text x={toX(Number(row.controls[xKey]), xMin, xMax) + 13} y={toY(Number(row.controls[yKey]), yMin, yMax) - 12} className="nt-plot-hover">{row.row_id} · {number(row.prediction, 1)} {meta.target.unit || ''}</text> : null })()}
              <text x={PAD.left} y={H - 10} className="nt-axis-label">{labelFor(meta, xKey)} / {xKey} → {unitFor(meta, xKey)}</text>
              <text transform={`rotate(-90 16 ${H - PAD.bottom})`} x="16" y={H - PAD.bottom} className="nt-axis-label">{labelFor(meta, yKey)} / {yKey} → {unitFor(meta, yKey)}</text>
            </svg>}
            <div className="nt-plot-legend"><span><i className="nt-dot nt-dot-known" />已观测实测</span><span><i className="nt-dot nt-dot-candidate" />未揭示候选</span><span><i className="nt-ring" />当前选择</span><em>候选强度标签不在前端；纵轴是配方控制量。</em></div>
          </div>}
      </div>
      {!hideAside && <div className="nt-atlas-aside">
        <div className="nt-atlas-readout">
          <span className="nt-kicker">SHARED SELECTION</span>
          {selected ? <>
            <h3>{selected.row_id}</h3>
            <span className="nt-state nt-state-open">历史实测未揭示</span>
            <strong>{number(selected.prediction, 2)} <em>{meta.target.unit || 'unit not supplied'} 预测</em></strong>
            <dl>{controlEntries(selected.controls).slice(0, 4).map(([key, value]) => <div key={key}><dt>{labelFor(meta, key)}</dt><dd>{number(value, 1)}</dd></div>)}</dl>
            <button type="button" className="nt-secondary-button" onClick={() => onCompare(selected.row_id)}><Columns2 size={14} /> {compareIds.includes(selected.row_id) ? '已加入对比' : '加入并排比较'}</button>
          </> : <p className="nt-muted">在航图或表格里选择一个候选。没有选择时，右侧详情不会编造数据。</p>}
        </div>
        {compare && <div className="nt-compare-mini"><span>并排对照</span><strong>{compare.row_id}</strong><p>{number(compare.prediction, 2)} {meta.target.unit || ''} 预测 · {number(compare.disagreement, 2)} {meta.target.unit || ''} 分歧</p><button type="button" className="nt-link-button" onClick={() => onSelect(compare.row_id)}>切换到这一条 <ArrowDown size={12} /></button></div>}
        {mode === 'research' && <div className="nt-research-note"><span>候选计数</span><code>{candidates.length}</code><span>策略</span><code>{view?.snapshot?.strategy ? strategyLabel(view.snapshot.strategy) : '预览'}</code><span>当前选择</span><code>{selected?.row_id || '—'}</code></div>}
      </div>}
    </div>
  </section>
}

function CandidateTable({ rows, selectedId, compareIds, onSelect, onCompare, mode, view, onFocusRow }) {
  const meta = useDataset()
  if (!rows.length) return <div className="nt-unavailable"><ShieldAlert size={16} /> 候选表格不可用：后端没有返回候选数据，不显示占位行。</div>
  const columns = mode === 'research' ? meta.features.map(item => item.key) : meta.features.slice(0, 3).map(item => item.key)
  return <div className="nt-table-wrap" role="region" aria-label="候选表格" tabIndex={0}>
    <table className="nt-candidate-table">
      <thead><tr><th>候选</th>{columns.map(key => <th key={key}>{labelFor(meta, key)} <small>{unitFor(meta, key)}</small></th>)}<th>预测 {meta.target.unit || ''}</th><th>分歧 {meta.target.unit || ''}</th><th>状态</th><th><span className="nt-sr">操作</span></th></tr></thead>
      <tbody>{rows.map((row, index) => {
        const state = candidateState(row.row_id, view, selectedId, compareIds)
        return <tr key={row.row_id} id={`nt-candidate-${row.row_id}`} tabIndex="0" aria-selected={selectedId === row.row_id}
          className={selectedId === row.row_id ? 'is-selected' : ''} onClick={() => onSelect(row.row_id)} onKeyDown={event => onFocusRow(event, index)}>
          <td><code>{row.row_id}</code></td>{columns.map(key => <td key={key}>{number(row.controls[key], 1)}</td>)}
          <td>{number(row.prediction, 2)}</td><td>{row.disagreement == null ? '—' : number(row.disagreement, 2)}</td>
          <td><span className={`nt-table-state nt-table-${state}`}>{state === 'pending' ? '已封存' : state === 'selected' ? '当前' : state === 'compare' ? '对比' : state === 'revealed' ? '已揭示' : '未揭示'}</span></td>
          <td>{mode === 'research' && <button type="button" className="nt-link-button" onClick={event => { event.stopPropagation(); onCompare(row.row_id) }}><Columns2 size={12} /> 对比</button>}</td>
        </tr>
      })}</tbody>
    </table>
  </div>
}
