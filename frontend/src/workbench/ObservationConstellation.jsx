import React, { useMemo, useState } from 'react'
import { ArrowUpRight, Crosshair } from 'lucide-react'
import { number } from './data'
import { useDataset } from './dataset'

const WIDTH = 900
const HEIGHT = 620

function extent(rows, key) {
  const values = rows.map(row => Number(row[key])).filter(Number.isFinite)
  return values.length ? [Math.min(...values), Math.max(...values)] : [0, 1]
}

function ratio(value, bounds) {
  return Math.max(0, Math.min(1, (Number(value) - bounds[0]) / Math.max(bounds[1] - bounds[0], 1e-9)))
}

function position(values, bounds) {
  const longitude = (ratio(values[0], bounds[0]) - .5) * Math.PI * 1.75
  const latitude = (ratio(values[1], bounds[1]) - .5) * Math.PI * .88
  const depth = Math.cos(latitude) * Math.cos(longitude)
  return {
    x: 450 + 278 * Math.cos(latitude) * Math.sin(longitude),
    y: 312 - 232 * Math.sin(latitude) - (ratio(values[2], bounds[2]) - .5) * 32,
    depth,
    strength: ratio(values[2], bounds[2]),
  }
}

export default function ObservationConstellation({
  landscape, selectedCandidate, compareCandidate, selection, onSelectObserved,
}) {
  const meta = useDataset()
  const [focusIndex, setFocusIndex] = useState(0)
  const rows = landscape?.rows || []
  const xKey = meta.features[0]?.key
  const yKey = meta.features[1]?.key
  const targetKey = meta.target.key
  const points = useMemo(() => {
    const bounds = [extent(rows, xKey), extent(rows, yKey), extent(rows, targetKey)]
    const observed = rows.map(row => ({ row, ...position([row[xKey], row[yKey], row[targetKey]], bounds) }))
    const candidate = item => item ? position([item.controls?.[xKey], item.controls?.[yKey], item.prediction], bounds) : null
    return { observed, candidateA: candidate(selectedCandidate), candidateB: candidate(compareCandidate) }
  }, [rows, xKey, yKey, targetKey, selectedCandidate, compareCandidate])

  function moveFocus(event) {
    if (!rows.length || !['ArrowRight', 'ArrowLeft'].includes(event.key)) return
    event.preventDefault()
    const next = (focusIndex + (event.key === 'ArrowRight' ? 1 : -1) + rows.length) % rows.length
    setFocusIndex(next)
    onSelectObserved?.(rows[next])
  }

  return <section className="nt-constellation" aria-labelledby="nt-constellation-title">
    <header className="nt-constellation-head">
      <div><span>OBSERVATION FIELD / TRAIN ONLY</span><h2 id="nt-constellation-title">已知实验的星图</h2></div>
      <strong>{rows.length || '—'} <small>条真实记录</small></strong>
    </header>
    <div className="nt-constellation-canvas">
      {rows.length ? <svg viewBox={'0 0 ' + WIDTH + ' ' + HEIGHT} role="img" tabIndex="0"
        onKeyDown={moveFocus} aria-label={'已观测训练记录的视觉投影，使用左右方向键逐条查看；' + meta.features[0]?.displayName + ' 与 ' + meta.features[1]?.displayName + ' 决定点位，' + meta.target.displayName + ' 影响亮度。'}>
        <defs>
          <radialGradient id="nt-orb-halo"><stop offset="0" stopColor="#39bfc2" stopOpacity=".18" /><stop offset=".65" stopColor="#1f829e" stopOpacity=".08" /><stop offset="1" stopColor="#07131d" stopOpacity="0" /></radialGradient>
          <radialGradient id="nt-orb-core"><stop offset="0" stopColor="#b6fff1" stopOpacity=".8" /><stop offset=".45" stopColor="#57d8d0" stopOpacity=".26" /><stop offset="1" stopColor="#57d8d0" stopOpacity="0" /></radialGradient>
          <filter id="nt-orb-glow"><feGaussianBlur stdDeviation="4" /></filter>
        </defs>
        <circle cx="450" cy="310" r="310" fill="url(#nt-orb-halo)" />
        <g className="nt-orbit-guides" aria-hidden="true">
          <ellipse cx="450" cy="310" rx="279" ry="234" />
          <ellipse cx="450" cy="310" rx="278" ry="79" />
          <ellipse cx="450" cy="310" rx="128" ry="234" />
          <ellipse cx="450" cy="310" rx="278" ry="91" transform="rotate(-28 450 310)" />
          <path d="M102 455 C280 578 595 596 798 425" />
        </g>
        <circle cx="450" cy="310" r="208" fill="url(#nt-orb-core)" opacity=".42" />
        <g className="nt-orb-stars">
          {points.observed.map(({ row, x, y, depth, strength }, index) => {
            const selected = selection?.kind === 'observed' && selection.rowId === row._row_id
            const radius = 1.4 + strength * 2 + Math.max(0, depth) * 1.3
            return <circle key={row._row_id} cx={x} cy={y} r={selected ? radius + 3 : radius}
              className={selected ? 'is-selected' : depth < .15 ? 'is-far' : ''}
              style={{ opacity: selected ? 1 : .48 + Math.max(0, depth) * .46 }}
              onClick={() => onSelectObserved?.(row)}>
              <title>{row._row_id + ' · 实测 ' + number(row[targetKey], 2) + ' ' + (meta.target.unit || '')}</title>
            </circle>
          })}
        </g>
        {points.candidateB && compareCandidate?.row_id !== selectedCandidate?.row_id && <g className="nt-orb-marker is-compare" transform={'translate(' + points.candidateB.x + ' ' + points.candidateB.y + ')'}>
          <circle r="12" /><path d="M-18 0H18M0-18V18" /><text x="24" y="-15">B / {compareCandidate.row_id}</text>
        </g>}
        {points.candidateA && <g className="nt-orb-marker is-primary" transform={'translate(' + points.candidateA.x + ' ' + points.candidateA.y + ')'}>
          <circle r="19" /><circle r="32" className="nt-orb-pulse" /><path d="M-26 0H26M0-26V26" /><text x="39" y="-18">A / {selectedCandidate.row_id}</text>
        </g>}
        <text x="50" y="70" className="nt-orb-axis">01 / {meta.features[0]?.displayName || '字段一'}</text>
        <text x="50" y="92" className="nt-orb-axis">02 / {meta.features[1]?.displayName || '字段二'}</text>
        <text x="50" y="114" className="nt-orb-axis">光点 / {meta.target.displayName}</text>
        <text x="638" y="560" className="nt-orb-coordinate">VISUAL PROJECTION</text>
      </svg> : <div className="nt-constellation-empty"><Crosshair size={22} /><span>正在读取已观测记录。没有数据时不生成星点。</span></div>}
      <div className="nt-constellation-ledger" aria-hidden="true"><span>FIELD / {meta.shortId || meta.id}</span><span>OBSERVED {rows.length || '—'}</span><ArrowUpRight size={14} /></div>
    </div>
    <footer><span><i className="nt-orb-legend-dot" /> 已观测实测</span><span><i className="nt-orb-legend-cross" /> 待看方案</span><p>星图是视觉投影，不是材料的物理空间；亮点和暗点不表示概率。</p></footer>
  </section>
}
