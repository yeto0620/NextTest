import React, { useMemo, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, ArrowRight, Check, CircleDot, FileText, Fingerprint, LockKeyhole, ShieldCheck, Upload, X } from 'lucide-react'
import { CONTROL_LABELS } from './data'

const ROLE_OPTIONS = [
  ['control', '可控制变量', 'control'], ['context', '环境/上下文', 'context'],
  ['target', '实验结果', 'target'], ['posthoc', '事后信息', 'posthoc'], ['ignored', '忽略', 'ignored'],
]

async function api(path, method = 'GET', body, raw = false) {
  const response = await fetch(path, { method, headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `请求失败（${response.status}）`)
  return data
}

function defaultRoles(columns) {
  const numeric = columns.filter(c => c.numeric).map(c => c.name)
  const target = numeric[numeric.length - 1] || columns[columns.length - 1]?.name
  const roles = {}
  columns.forEach((column, index) => {
    if (column.name === target) roles[column.name] = 'target'
    else if (column.numeric && numeric.indexOf(column.name) < 5) roles[column.name] = 'control'
    else roles[column.name] = 'ignored'
  })
  return { roles, target }
}

function StepRail({ step, research = false }) {
  return <div className="nt-dock-steps" aria-label="数据入舱步骤">
    {(research ? [['1', 'D1', '登记'], ['2', 'D2', '字段'], ['3', 'D3', '闸门'], ['4', 'D4', '冻结']] : [['1', 'D1', '文件登记'], ['2', 'D2', '字段角色'], ['3', 'D3', '安全闸门'], ['4', 'D4', '冻结启航']]).map(([number, code, label]) => <div key={code} className={`nt-dock-step ${Number(number) === step ? 'is-active' : ''} ${Number(number) < step ? 'is-done' : ''}`}><span>{Number(number) < step ? <Check size={11} /> : number}</span><div><small>{code}</small><strong>{label}</strong></div></div>)}
  </div>
}

export default function DataDock({ onClose, onComplete, onUseDemo, mode = 'explore' }) {
  const research = mode === 'research'
  const [step, setStep] = useState(1)
  const [intake, setIntake] = useState(null)
  const [schemaPayload, setSchemaPayload] = useState(null)
  const [gate, setGate] = useState(null)
  const [ack, setAck] = useState(null)
  const [dataset, setDataset] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)
  const [roles, setRoles] = useState({})
  const [displayNames, setDisplayNames] = useState({})
  const [units, setUnits] = useState({})
  const [datasetName, setDatasetName] = useState('')
  const [ackIds, setAckIds] = useState([])

  const columns = intake?.intake?.column_meta || []
  const warnings = gate?.warnings || []
  const gateReady = Boolean(gate)
  const canSchema = useMemo(() => {
    const values = Object.values(roles)
    return columns.length > 0 && values.filter(v => v === 'target').length === 1 && values.filter(v => v === 'control').length >= 2
  }, [roles, columns])

  async function upload(file) {
    if (!file) return
    setBusy(true); setError(''); setIntake(null); setGate(null); setAck(null); setDataset(null); setStep(1)
    try {
      const response = await fetch('/api/intakes', { method: 'POST', headers: { 'Content-Type': 'text/csv', 'X-NextTest-Filename': encodeURIComponent(file.name) }, body: file, cache: 'no-store' })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `上传失败（${response.status}）`)
      setIntake(data)
      const defaults = defaultRoles(data.intake.column_meta)
      setRoles(defaults.roles); setDisplayNames(Object.fromEntries(data.intake.columns.map(c => [c, c]))); setUnits(Object.fromEntries(data.intake.columns.map(c => [c, '']))); setDatasetName(data.intake.filename.replace(/\.csv$/i, ''))
      setStep(2)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  async function confirmSchema() {
    if (!intake) return null
    setBusy(true); setError('')
    try {
      const data = await api(`/api/intakes/${intake.intake.intake_id}/schema`, 'POST', { roles, display_names: displayNames, units, dataset_name: datasetName })
      setSchemaPayload(data.schema); setGate(null); setAck(null); setDataset(null)
      return data.schema
    } catch (err) { setError(err.message); throw err } finally { setBusy(false) }
  }

  async function runGate() {
    setBusy(true); setError('')
    try {
      const schema = schemaPayload || await confirmSchema()
      if (!schema) return
      const data = await api(`/api/intakes/${intake.intake.intake_id}/gate`, 'POST')
      setGate(data); setAck(null); setAckIds([]); setStep(3)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  async function acknowledgeAndContinue() {
    setBusy(true); setError('')
    try {
      const data = await api(`/api/intakes/${intake.intake.intake_id}/acknowledge`, 'POST', { warning_ids: ackIds })
      setAck(data); setStep(4)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  async function freeze() {
    setBusy(true); setError('')
    try {
      const data = await api(`/api/intakes/${intake.intake.intake_id}/freeze`, 'POST')
      setDataset(data.dataset); setStep(4)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return <div className="nt-dock-layer" role="dialog" aria-modal="true" aria-labelledby="nt-dock-title">
    <div className="nt-dock">
      <header className="nt-dock-head"><div><span className="nt-kicker">DATA DOCK / 数据入舱</span><h2 id="nt-dock-title">{research ? '数据入舱' : '先给字段定角色，再让模型看数据。'}</h2>{research ? <p className="nt-dock-compact-copy">本机处理 · 字段确认 · 闸门冻结</p> : <p>文件只在本机处理，不上传网络。当前支持 UTF-8 数值型单目标回归，最多 20,000 行、64 列、10 MiB。</p>}</div><div className="nt-dock-head-actions"><span className="nt-dock-local"><span className="nt-signal" /> LOCAL DATASET</span><button type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭 Data Dock">×</button></div></header>
      <StepRail step={step} research={research} />
      {error && <div className="nt-dock-error" role="alert"><AlertTriangle size={14} /> {error}</div>}
      {step === 1 && <section className="nt-dock-panel">
        <div className="nt-dropzone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); upload(e.dataTransfer.files?.[0]) }}>
          <Upload size={28} /><h3>{research ? '导入 CSV' : '选择一份 CSV'}</h3>{research ? <p className="nt-dock-compact-copy">UTF-8 · 单目标回归 · ≤ 10 MiB</p> : <p>UTF-8 / UTF-8-SIG；数值型单目标回归；不做自动填补、编码或单位换算。</p>}<button type="button" className="nt-primary" onClick={() => fileRef.current?.click()} disabled={busy}>{busy ? '正在登记…' : '选择 CSV'}</button><input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={e => upload(e.target.files?.[0])} /></div>
        <div className="nt-dock-alternative"><button type="button" className="nt-link-button" onClick={onUseDemo || onClose}>继续使用 Concrete 示例 <ArrowRight size={13} /></button><span>当前示例不会被替换；导入会先进入独立的 intake。</span></div>
        {intake && <div className="nt-intake-card"><span className="nt-kicker">REGISTERED / 文件登记</span><h3>{intake.intake.filename}</h3><div className="nt-intake-facts"><span>行 {intake.intake.rows}</span><span>列 {intake.intake.columns.length}</span><span>{intake.intake.bytes} bytes</span><span>{intake.intake.encoding}</span></div><code className="nt-hash">{intake.intake.input_sha256}</code><div className="nt-preview-table"><table><thead><tr>{intake.intake.columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{intake.intake.preview.map((row, i) => <tr key={i}>{intake.intake.columns.map(c => <td key={c}>{row[c] == null ? '—' : String(row[c])}</td>)}</tr>)}</tbody></table></div><p className="nt-dock-note">尚未建立训练/候选/留出；下一步才确认哪些列能用于决策。</p><div className="nt-dock-actions"><button type="button" className="nt-link-button" onClick={() => setStep(1)}>重新选择</button><button type="button" className="nt-primary" onClick={() => setStep(2)}>继续字段角色 <ArrowRight size={14} /></button></div></div>}
      </section>}

      {step === 2 && intake && <section className="nt-dock-panel"><div className="nt-dock-grid"><div><span className="nt-kicker">D2 / FIELD ROLES</span><h3>每列只能有一个角色</h3><p className="nt-dock-note">系统给出的是建议，尚未确认。target 不能同时作为 feature；非数值列只能选 post-hoc 或 ignored。</p><label className="nt-dock-field">数据集显示名<input value={datasetName} onChange={e => setDatasetName(e.target.value)} maxLength={100} /></label><div className="nt-role-table"><table><thead><tr><th>原列名</th><th>示例</th><th>类型</th><th>缺失</th><th>唯一</th><th>角色</th><th>显示名</th><th>单位</th></tr></thead><tbody>{columns.map(column => <tr key={column.name}><td><code>{column.name}</code></td><td>{String(intake.intake.preview?.[0]?.[column.name] ?? '—')}</td><td>{column.numeric ? 'numeric' : 'text'}</td><td>{column.missing}</td><td>{column.unique}</td><td><select value={roles[column.name] || 'ignored'} onChange={e => setRoles(prev => ({ ...prev, [column.name]: e.target.value }))}>{ROLE_OPTIONS.map(([value, label, code]) => <option key={value} value={value} disabled={!column.numeric && !['posthoc', 'ignored'].includes(value)}>{mode === 'research' ? `${label} / ${code}` : label}</option>)}</select></td><td><input value={displayNames[column.name] || ''} maxLength={80} onChange={e => setDisplayNames(prev => ({ ...prev, [column.name]: e.target.value }))} /></td><td><input value={units[column.name] || ''} maxLength={40} placeholder="unit not supplied" onChange={e => setUnits(prev => ({ ...prev, [column.name]: e.target.value }))} /></td></tr>)}</tbody></table></div><p className="nt-dock-note">单位是你声明的 metadata；NextTest 标为 <code>unit_not_verified</code>，本轮不验证、不换算。</p><div className="nt-dock-actions"><button type="button" className="nt-link-button" onClick={() => setStep(1)}><ArrowLeft size={13} /> 返回文件</button><button type="button" className="nt-primary" disabled={busy || !canSchema} onClick={runGate}>确认角色并检查 <ArrowRight size={14} /></button></div></div><aside className="nt-dock-questions"><h4>如果你是第一次看这份表</h4><p>1. 实验前能调的是哪几列？</p><p>2. 最终测量结果是哪一列？</p><p>3. 哪些信息只有实验结束后才知道？</p><div>不确定时，先选 ignored；不要在角色未确认时开始训练。</div></aside></div></section>}

      {step === 3 && gate && <section className="nt-dock-panel"><div className="nt-gate-heading"><div><span className="nt-kicker">D3 / SAFETY GATE</span><h3>数据质量与泄漏闸门</h3><p>BLOCKED / WARNING / PASSED 是三件不同的事实；这不是健康分。</p></div><span className={`nt-gate-stamp is-${gate.status.toLowerCase()}`}>{gate.status}</span></div>{gate.status === 'BLOCKED' && <div className="nt-gate-blocked"><AlertTriangle size={18} /><div><strong>必须修复后才能继续</strong>{gate.errors.map(e => <p key={e.code + (e.column || '')}><b>{e.column || '数据'}</b>：{e.message}</p>)}</div></div>}{gate.status === 'WARNING' && <div className="nt-gate-warning"><AlertTriangle size={17} /><div><strong>需要逐项确认，确认不表示风险消失</strong><p>警告提示需要人工判断，不自动证明该列泄漏。</p>{gate.warnings.map(w => <label key={w.id} className="nt-warning-check"><input type="checkbox" checked={ackIds.includes(w.id)} onChange={e => setAckIds(prev => e.target.checked ? [...prev, w.id] : prev.filter(id => id !== w.id))} /><span><b>{w.title}</b><small>{w.message}</small></span></label>)}</div></div>}{gate.status === 'PASSED' && <div className="nt-gate-passed"><ShieldCheck size={18} /><div><strong>通过当前软件闸门</strong><p>通过表示满足当前软件检查，不表示数据没有科学偏差。</p></div></div>}<div className="nt-gate-facts"><h4>实际检查过的事实</h4>{gate.facts.map((fact, i) => <p key={i}><CircleDot size={11} /> {fact}</p>)}</div><div className="nt-gate-diagnostics"><h4>Research 诊断</h4><div>{gate.split_counts ? `拟议切分 ${gate.split_counts.train} / ${gate.split_counts.candidate} / ${gate.split_counts.test}` : '切分不可用'}<br />{gate.warnings.length} 条启发式 warning · 输入 {gate.input_sha256.slice(0, 12)}… · schema {gate.schema_sha256.slice(0, 12)}…</div></div><div className="nt-dock-actions"><button type="button" className="nt-link-button" onClick={() => setStep(2)}><ArrowLeft size={13} /> 修改角色</button>{gate.status === 'BLOCKED' ? <button type="button" className="nt-primary" disabled>冻结并进入工作台</button> : gate.status === 'WARNING' ? <button type="button" className="nt-primary" disabled={busy || ackIds.length !== gate.warnings.length} onClick={acknowledgeAndContinue}>确认全部 {gate.warnings.length} 条警告 <ArrowRight size={14} /></button> : <button type="button" className="nt-primary" onClick={() => setStep(4)}>继续到冻结 <ArrowRight size={14} /></button>}</div></section>}

      {step === 4 && gate && <section className="nt-dock-panel"><div className="nt-freeze-grid"><div><span className="nt-kicker">D4 / FREEZE & LAUNCH</span><h3>确认这份数据护照</h3><p>冻结后角色、单位、切分和警告确认都不可原地修改；改角色必须新建 intake。</p><div className="nt-freeze-summary"><div><span>训练使用</span><strong>{gate.split_counts?.train ?? '—'} 行 · {Object.values(roles).filter(r => r === 'control' || r === 'context').length} 个 feature</strong></div><div><span>隐藏结果</span><strong>{gate.split_counts?.candidate ?? '—'} 条候选；{gate.split_counts?.test ?? '—'} 条独立留出</strong></div><div><span>切分方式</span><strong>固定 control recipe 分组 60/20/20</strong></div><div><span>警告确认</span><strong>{warnings.length ? `${warnings.length} 条 · 用户已逐项确认` : '无 warning'}</strong></div><div><span>单位状态</span><strong>用户声明 · unit_not_verified</strong></div></div><div className="nt-dock-actions"><button type="button" className="nt-link-button" onClick={() => setStep(3)}><ArrowLeft size={13} /> 返回检查</button>{dataset ? <button type="button" className="nt-primary" onClick={() => onComplete(dataset)}>进入观测站 <ArrowRight size={15} /></button> : <button type="button" className="nt-primary" disabled={busy} onClick={freeze}>{busy ? '正在冻结…' : '冻结数据护照'} <LockKeyhole size={15} /></button>}</div></div><aside className="nt-passport"><div className="nt-passport-top"><Fingerprint size={17} /><span>DATASET PASSPORT</span><span className={`nt-passport-seal is-${gate.status.toLowerCase()}`}>{gate.status}</span></div><dl><dt>样本名</dt><dd>{datasetName || intake?.intake?.filename}</dd><dt>原始文件</dt><dd>{intake?.intake?.rows} rows · {intake?.intake?.columns?.length} columns · {intake?.intake?.bytes} B</dd><dt>文件指纹</dt><dd><code>{gate.input_sha256.slice(0, 18)}…</code></dd><dt>角色指纹</dt><dd><code>{gate.schema_sha256.slice(0, 18)}…</code></dd><dt>闸门状态</dt><dd>{gate.status} · {warnings.length} warnings</dd><dt>切分</dt><dd>{gate.split_counts?.train ?? '—'} / {gate.split_counts?.candidate ?? '—'} / {gate.split_counts?.test ?? '—'} · grouped</dd></dl>{dataset && <div className="nt-passport-issued"><Check size={14} /> 已冻结 · {dataset.short_id}</div>}</aside></div></section>}

      <footer className="nt-dock-foot"><span><FileText size={12} /> 只在本机处理；不联网、不调用 LLM</span><span>Data Dock · 历史数据回放</span></footer>
    </div>
  </div>
}
