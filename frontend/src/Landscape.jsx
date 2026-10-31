import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { LocateFixed, Maximize2, RotateCcw } from 'lucide-react'
import { useDataset, labelFor, unitFor } from './workbench/dataset'

export const CONTROLS = {
  Cement: '水泥', Water: '水', BlastFurnaceSlag: '矿渣', FlyAsh: '粉煤灰',
  Superplasticizer: '减水剂', CoarseAggregate: '粗骨料', FineAggregate: '细骨料',
}

function normalize(value, low, high) { return ((value - low) / Math.max(high - low, 0.0001) - 0.5) * 9 }

function Bars({ points, onPick, onHover }) {
  const ref = useRef()
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const color = useMemo(() => new THREE.Color(), [])
  useEffect(() => {
    if (!ref.current) return
    points.forEach((point, index) => {
      dummy.position.set(point.x, point.height / 2, point.z)
      dummy.scale.set(1, point.height, 1)
      dummy.updateMatrix()
      ref.current.setMatrixAt(index, dummy.matrix)
      color.set('#32b7c2').lerp(new THREE.Color('#e3b663'), point.strength / 100)
      ref.current.setColorAt(index, color)
    })
    ref.current.instanceMatrix.needsUpdate = true
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true
  }, [points, dummy, color])
  if (!points.length) return null
  return <instancedMesh ref={ref} args={[null, null, points.length]}
    onPointerMove={e => { e.stopPropagation(); onHover(points[e.instanceId]) }}
    onPointerOut={() => onHover(null)}
    onClick={e => { e.stopPropagation(); onPick(points[e.instanceId]) }}>
    <cylinderGeometry args={[0.075, 0.075, 1, 7]} />
    <meshStandardMaterial roughness={0.38} metalness={0.12} />
  </instancedMesh>
}

function Scene({ points, pendingPoint, onPick, onHover, controlsRef }) {
  return <>
    <color attach="background" args={['#0c1c28']} />
    <fog attach="fog" args={['#0c1c28', 13, 25]} />
    <ambientLight intensity={1.3} />
    <directionalLight position={[4, 9, 5]} intensity={2.2} color="#d8f7fa" />
    <pointLight position={[-5, 4, -3]} intensity={22} color="#28b8c8" />
    <gridHelper args={[11, 11, '#285063', '#204052']} position={[0, 0.01, 0]} />
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.035, 0]}>
      <planeGeometry args={[11, 11]} />
      <meshStandardMaterial color="#102938" roughness={0.9} />
    </mesh>
    <Bars points={points} onPick={onPick} onHover={onHover} />
    {pendingPoint && <group position={[pendingPoint.x, 0, pendingPoint.z]}>
      <mesh position={[0, pendingPoint.height / 2, 0]} scale={[1, pendingPoint.height, 1]}>
        <cylinderGeometry args={[0.19, 0.19, 1, 16]} />
        <meshStandardMaterial color="#ffcb69" emissive="#8b4b0b" emissiveIntensity={0.65} metalness={0.24} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.035, 0]}>
        <ringGeometry args={[0.33, 0.43, 48]} />
        <meshBasicMaterial color="#ffcb69" side={THREE.DoubleSide} />
      </mesh>
    </group>}
    <OrbitControls ref={controlsRef} enableDamping minDistance={6} maxDistance={19}
      maxPolarAngle={Math.PI / 2.04} minPolarAngle={0.15} target={[0, 1.9, 0]} />
  </>
}

class SceneError extends React.Component {
  constructor(props) { super(props); this.state = { failed: false } }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <div className="scene-fallback">当前浏览器无法显示三维视图。项目回放功能仍可使用。</div> : this.props.children }
}

export default function Landscape({ landscape, pending, selectedId, onSelectObserved }) {
  const meta = useDataset()
  const [xKey, setXKey] = useState(meta.features[0]?.key || 'x')
  const [zKey, setZKey] = useState(meta.features[1]?.key || 'y')
  const [minStrength, setMinStrength] = useState(0)
  useEffect(() => {
    if (!meta.features.some(item => item.key === xKey)) setXKey(meta.features[0]?.key || 'x')
    if (!meta.features.some(item => item.key === zKey)) setZKey(meta.features[1]?.key || 'y')
  }, [meta.features])
  const [hover, setHover] = useState(null)
  const [picked, setPicked] = useState(null)
  const controlsRef = useRef(null)
  const rows = landscape?.rows || []
  const axes = useMemo(() => {
    if (!rows.length) return null
    return { xMin: Math.min(...rows.map(r => r[xKey])), xMax: Math.max(...rows.map(r => r[xKey])),
      zMin: Math.min(...rows.map(r => r[zKey])), zMax: Math.max(...rows.map(r => r[zKey])) }
  }, [rows, xKey, zKey])
  const points = useMemo(() => !axes ? [] : rows.filter(r => Number(r[meta.target.key]) >= minStrength).map(r => ({
    id: r._row_id, strength: Number(r[meta.target.key]), xValue: r[xKey], zValue: r[zKey],
    x: normalize(r[xKey], axes.xMin, axes.xMax), z: normalize(r[zKey], axes.zMin, axes.zMax),
    height: 0.2 + Number(r[meta.target.key]) / 17,
  })), [rows, axes, xKey, zKey, minStrength])
  const pendingPoint = useMemo(() => !pending || !axes ? null : ({
    x: normalize(pending.controls[xKey], axes.xMin, axes.xMax),
    z: normalize(pending.controls[zKey], axes.zMin, axes.zMax),
    height: 0.2 + Math.max(0, pending.prediction) / 17,
  }), [pending, axes, xKey, zKey])
  const selected = hover || points.find(point => point.id === selectedId) || picked

  function focusPending() {
    if (!pendingPoint || !controlsRef.current) return
    const controls = controlsRef.current
    controls.target.set(pendingPoint.x, 1.8, pendingPoint.z)
    controls.object.position.set(pendingPoint.x + 3.4, 6.6, pendingPoint.z + 5.2)
    controls.update()
    setPicked(null)
  }

  return <section className="landscape-card" id="space">
    <div className="panel-heading"><div><span className="eyebrow">01 / MATERIAL LANDSCAPE</span><h2>把已知配方，变成可探索的空间</h2><p>每根细柱是一条历史实测。拖动旋转，点击查看配方。</p></div><div className="panel-count"><strong>{points.length}</strong><span>/ {rows.length} 条已知记录</span></div></div>
    <div className="plot-toolbar">
      <label>横轴 · 原料<select value={xKey} onChange={e => { setXKey(e.target.value); setPicked(null) }}>{meta.features.map(feature => <option key={feature.key} value={feature.key} disabled={feature.key === zKey}>{feature.displayName} / {feature.key}</option>)}</select></label>
      <label>纵轴 · 原料<select value={zKey} onChange={e => { setZKey(e.target.value); setPicked(null) }}>{meta.features.map(feature => <option key={feature.key} value={feature.key} disabled={feature.key === xKey}>{feature.displayName} / {feature.key}</option>)}</select></label>
      <label className="range-label">实测 {meta.target.displayName} ≥ <strong>{minStrength} {meta.target.unit || ''}</strong><input aria-label="筛选已知强度" type="range" min="0" max="100" step="5" value={minStrength} onChange={e => setMinStrength(Number(e.target.value))} /></label>
      {pendingPoint && <button className="focus-button" type="button" onClick={focusPending}><LocateFixed size={16}/> 定位待验证方案</button>}
      <button className="icon-button" type="button" aria-label="重置三维视角" title="重置视角" onClick={() => controlsRef.current?.reset()}><RotateCcw size={17} /></button>
    </div>
    <div className="scene-wrap">
      <SceneError><Canvas camera={{ position: [7.5, 8.2, 10.5], fov: 44 }} dpr={[1, 1.6]}>
        <Scene points={points} pendingPoint={pendingPoint} onPick={point => { setPicked(point); onSelectObserved?.(point) }} onHover={setHover} controlsRef={controlsRef} />
      </Canvas></SceneError>
      <div className="scene-topline"><span className="live-dot" /> OBSERVED DATA ONLY <span className="scene-separator">/</span> AGE 28 DAYS</div>
      <div className="scene-axes">X · {labelFor(meta, xKey)} <span>Y · {meta.target.displayName}</span> Z · {labelFor(meta, zKey)}</div>
      <div className="scene-legend"><span><i className="legend-cyan" />历史实测</span><span><i className="legend-amber" />待验证预测</span></div>
      {pendingPoint && <div className="prediction-flag">待验证方案 · {pending.row_id}<strong>{Number(pending.prediction).toFixed(1)} {meta.target.unit || ''}</strong><small>模型预测，实测未揭示</small></div>}
      {selected && <div className="point-readout"><small>历史实测 / {selected.id}</small><strong>{selected.strength.toFixed(2)} <em>{meta.target.unit || ''}</em></strong><span>{CONTROLS[xKey]} {selected.xValue.toFixed(1)} · {CONTROLS[zKey]} {selected.zValue.toFixed(1)} kg/m³</span></div>}
      {!rows.length && <div className="scene-fallback">正在加载已知材料记录…</div>}
      {rows.length > 0 && points.length === 0 && <div className="scene-fallback">这个筛选值下没有已知记录。请调低强度门槛。</div>}
    </div>
    <div className="plot-note"><Maximize2 size={16} /><span>三维位置只展示配方与强度的关联，不代表因果关系。琥珀色柱是尚未揭示结果的<strong>预测</strong>；候选集和独立留出集的真实强度不进入此图。</span></div>
  </section>
}
