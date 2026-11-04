import React from 'react'
import { Crosshair, Database } from 'lucide-react'
import { number } from './data'
import { useDataset, labelFor, unitFor } from './dataset'

const W = 640
const H = 330
const PAD = { left: 54, right: 22, top: 38, bottom: 42 }

function range(rows, key) {
  const values = rows.map(row => Number(row[key])).filter(Number.isFinite)
  return values.length ? [Math.min(...values), Math.max(...values)] : [0, 1]
}
function project(value, low, high, start, span) {
  return start + ((Number(value) - low) / Math.max(high - low, 0.0001)) * span
}

export default function ObservationPlate({ landscape, selectedCandidate, compareCandidate, selection, onSelectObserved, mode = 'explore' }) {
  const meta = useDataset()
  const rows = landscape?.rows || []
  const xKey = meta.features[0]?.key
  const yKey = meta.features[1]?.key
  const [xMin, xMax] = range(rows, xKey)
  const [yMin, yMax] = range(rows, yKey)
  const sx = value => project(value, xMin, xMax, PAD.left, W - PAD.left - PAD.right)
  const sy = value => project(value, yMin, yMax, H - PAD.bottom, -(H - PAD.top - PAD.bottom))
  const selectedId = selection?.kind === 'observed' ? selection.rowId : null
  const pointRadius = strength => 1.1 + Math.max(0, Math.min(100, Number(strength))) / 48
  return <section className="nt-plate" aria-labelledby="nt-plate-title">
    <div className="nt-plate-head">
      <div><span className="nt-kicker">{mode === 'research' ? 'OBSERVED DOMAIN / TRAIN ONLY' : 'OBSERVATION PLATE / OBSERVED ONLY'}</span><h2 id="nt-plate-title">{mode === 'research' ? '已知数据' : '先看见已经知道的区域'}</h2></div>
      <div className="nt-plate-count"><Database size={14} /><strong>{rows.length || '—'}</strong><span>条已观测记录</span></div>
    </div>
    <div className="nt-plate-chamber">
      {rows.length ? <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${meta.features[0]?.displayName || 'feature 1'} 与 ${meta.features[1]?.displayName || 'feature 2'} 的二维观测投影，点大小表示已观测 ${meta.target.displayName}`}>
        <defs>
          <pattern id="nt-grid" width="48" height="40" patternUnits="userSpaceOnUse"><path d="M48 0H0V40" fill="none" stroke="rgba(83,227,194,.13)" strokeWidth="1" /></pattern>
        </defs>
        <rect x={PAD.left} y={PAD.top} width={W - PAD.left - PAD.right} height={H - PAD.top - PAD.bottom} fill="url(#nt-grid)" />
        <path d={`M${PAD.left} ${PAD.top}V${H - PAD.bottom}H${W - PAD.right}`} className="nt-axis-line" />
        {[0, 1, 2, 3, 4].map(index => <g key={index}>
          <line x1={PAD.left} x2={W - PAD.right} y1={PAD.top + index * (H - PAD.top - PAD.bottom) / 4} y2={PAD.top + index * (H - PAD.top - PAD.bottom) / 4} className="nt-grid-line" />
          <text x={PAD.left - 9} y={PAD.top + index * (H - PAD.top - PAD.bottom) / 4 + 3} textAnchor="end" className="nt-axis-tick">{number(yMax - index * (yMax - yMin) / 4, 0)}</text>
        </g>)}
        {[0, 1, 2, 3, 4].map(index => <g key={index}>
          <line y1={PAD.top} y2={H - PAD.bottom} x1={PAD.left + index * (W - PAD.left - PAD.right) / 4} x2={PAD.left + index * (W - PAD.left - PAD.right) / 4} className="nt-grid-line" />
          <text x={PAD.left + index * (W - PAD.left - PAD.right) / 4} y={H - PAD.bottom + 18} textAnchor="middle" className="nt-axis-tick">{number(xMin + index * (xMax - xMin) / 4, 0)}</text>
        </g>)}
        {rows.map((row, index) => {
          const isSelected = selectedId === row._row_id
          return <circle key={row._row_id} cx={sx(row[xKey])} cy={sy(row[yKey])} r={pointRadius(row[meta.target.key])}
            className={`nt-observed-dot ${isSelected ? 'is-selected' : ''}`} style={{ '--arrival': `${Math.min(index * 8, 620)}ms` }}
            onClick={() => onSelectObserved?.(row)}>
            <title>{row._row_id} · 实测 {number(row[meta.target.key], 2)} {meta.target.unit || ''}</title>
          </circle>
        })}
        {selectedCandidate && <g className="nt-pending-marker" transform={`translate(${sx(selectedCandidate.controls[xKey])} ${sy(selectedCandidate.controls[yKey])})`} aria-label={`待验证方案 ${selectedCandidate.row_id}`}>
          <circle r="13" /><path d="M-20 0H20M0-20V20" /><text x="17" y="-12">PROPOSED / {selectedCandidate.row_id}</text>
        </g>}
        {compareCandidate && compareCandidate.row_id !== selectedCandidate?.row_id && <g className="nt-compare-marker" transform={`translate(${sx(compareCandidate.controls[xKey])} ${sy(compareCandidate.controls[yKey])})`} aria-label={`对比方案 ${compareCandidate.row_id}`}>
          <circle r="9" /><path d="M-12 0H12M0-12V12" />
        </g>}
        <text x={PAD.left} y={H - 10} className="nt-axis-label">{labelFor(meta, xKey)} / {xKey} → {unitFor(meta, xKey)}</text>
        <text transform={`rotate(-90 ${18} ${H - PAD.bottom})`} x={18} y={H - PAD.bottom} className="nt-axis-label">{labelFor(meta, yKey)} / {yKey} → {unitFor(meta, yKey)}</text>
        <line x1={PAD.left} x2={W - PAD.right} y1={PAD.top} y2={PAD.top} className="nt-scan-line" />
      </svg> : <div className="nt-plate-empty"><Crosshair size={20} /><span>正在读取已观测记录；没有数据时不生成示例点。</span></div>}
      <div className="nt-plate-meta"><span><i className="nt-dot nt-dot-known" />已观测实测</span><span><i className="nt-cross" />选中方案</span><span><i className="nt-cross nt-cross-muted" />对比方案</span><em>{mode === 'research' ? `size = ${meta.target.displayName} · correlation only` : `点大小 = ${meta.target.displayName} · 关联投影，不表示因果`}</em></div>
    </div>
    {landscape?.split_sha256 && <div className="nt-plate-foot"><span>来源：{meta.displayName} · {meta.isCustom ? 'LOCAL DATASET' : 'DEMO'} · 仅训练记录</span><code>split {landscape.split_sha256.slice(0, 12)}…</code></div>}
  </section>
}
