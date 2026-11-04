import React, { useEffect, useMemo, useState } from 'react'
import { ArrowRight, BotMessageSquare, Check, Circle, Clipboard, Database, FileText, LoaderCircle, MessageCircleQuestion, Orbit, Send, ShieldCheck, Sparkles, X } from 'lucide-react'

const MODES = [
  { id: 'candidate', label: '方案', icon: Sparkles, hint: '解释当前方案的公开配方、预测与预测差值异。' },
  { id: 'evidence', label: '证据', icon: FileText, hint: '解释已公布记录与只读审计事实。' },
  { id: 'defense', label: '答辩', icon: MessageCircleQuestion, hint: '整理已公开数字能说明什么、不能说明什么。' },
]

const QUICK_QUESTIONS = {
  candidate: ['为什么值得关注？', '差异应该怎么解释？'],
  evidence: ['当前证据能说明什么？', '哪些结论还不能下？'],
  defense: ['用三句话解释项目', '评委追问时如何说边界？'],
}

function missionSteps(view, selectedCandidate) {
  const snapshot = view?.snapshot
  const pending = view?.pending
  const revealed = snapshot?.revealed_count || 0
  const auditOk = Boolean(view?.audit && (view.audit.valid === true || view.audit.status))
  const facts = [
    { id: 'data', label: '数据闸门', detail: '字段、切分与泄漏检查', done: Boolean(snapshot) },
    { id: 'scan', label: '方案扫描', detail: '预测与预测差值异', done: Boolean(selectedCandidate || pending) },
    { id: 'freeze', label: '人工确认', detail: '选中后保存预测', done: Boolean(pending || revealed) },
    { id: 'observe', label: '证据回流', detail: '仅释放一条历史实测', done: revealed > 0 },
    { id: 'audit', label: '审计保存', detail: '更新模型与证据链', done: revealed > 0 && auditOk },
  ]
  const current = facts.findIndex(step => !step.done)
  return facts.map((step, index) => ({ ...step, state: step.done ? 'done' : index === current ? 'current' : 'waiting' }))
}

function detailMessage(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail
  if (typeof payload?.detail?.message === 'string') return payload.detail.message
  return fallback
}

export default function EvidenceAssistant({ open, onClose, view, selectedCandidate, onNavigate, onData }) {
  const [action, setAction] = useState('candidate')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [state, setState] = useState('idle')
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState(null)
  const projectId = view?.snapshot?.project_id || null
  const current = useMemo(() => MODES.find(item => item.id === action) || MODES[0], [action])
  const candidateReady = Boolean(selectedCandidate?.row_id)
  const canAsk = Boolean(projectId && (action !== 'candidate' || candidateReady) && question.length <= 500 && state !== 'loading')
  const steps = useMemo(() => missionSteps(view, selectedCandidate), [view, selectedCandidate])
  const nextStep = steps.find(step => step.state === 'current')

  useEffect(() => {
    if (!open) return undefined
    const onKey = event => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (!open) return undefined
    let cancelled = false
    fetch('/api/copilot/status', { cache: 'no-store' }).then(response => response.ok ? response.json() : null)
      .then(value => { if (!cancelled) setStatus(value) }).catch(() => { if (!cancelled) setStatus(null) })
    return () => { cancelled = true }
  }, [open])

  useEffect(() => {
    if (!open) return
    setAnswer(null); setState('idle'); setMessage('')
  }, [open, action, projectId, selectedCandidate?.row_id])

  if (!open) return null

  async function ask() {
    if (!canAsk) return
    setState('loading'); setMessage(''); setAnswer(null)
    const body = { action, project_id: projectId, question: question.trim() }
    if (action === 'candidate') body.candidate_id = selectedCandidate.row_id
    try {
      const endpoint = status?.configured ? '/api/copilot/explain' : '/api/agent/brief'
      const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), cache: 'no-store' })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        const code = data?.detail?.code
        setState(code === 'LLM_NOT_CONFIGURED' ? 'unconfigured' : 'error')
        setMessage(detailMessage(data, `请求失败（${response.status}）`))
        return
      }
      setAnswer(data); setState('answered')
    } catch {
      setState('error'); setMessage('证据助手当前不可用；未改变项目或实验记录。')
    }
  }

  return <div className="nt-assistant-layer" role="dialog" aria-modal="true" aria-labelledby="nt-assistant-title">
    <button type="button" className="nt-assistant-backdrop" onClick={onClose} aria-label="关闭证据助手" />
    <aside className="nt-assistant-panel">
      <header className="nt-assistant-head">
        <div><span className="nt-kicker">BOUNDED RESEARCH AGENT</span><h2 id="nt-assistant-title">AI 助手</h2><p>本地工具链负责流程；DeepSeek 只解释公开证据。</p></div>
        <button type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭证据助手"><X size={16} /></button>
      </header>
      <section className="nt-agent-orbit" aria-label="AI 助手任务链">
        <div className="nt-agent-orbit-head"><div><span className="nt-kicker">MISSION TRACE</span><strong>{nextStep ? `当前：${nextStep.label}` : '本轮证据已闭环'}</strong></div><span className={`nt-agent-link ${status?.configured ? 'is-online' : ''}`}><i />{status?.configured ? `${status.provider} 已配置` : '本地引擎可用'}</span></div>
        <div className="nt-agent-track">{steps.map((step, index) => <div key={step.id} className={`nt-agent-step is-${step.state}`}><span className="nt-agent-node">{step.done ? <Check size={11} /> : step.state === 'current' ? <Circle size={10} /> : index + 1}</span><div><strong>{step.label}</strong><small>{step.detail}</small></div></div>)}</div>
        <div className="nt-agent-authority"><ShieldCheck size={13} /><span>算法排序是权威结果；LLM 无选点、改模型或读取隐藏标签权限。</span></div>
        {!projectId ? <button type="button" className="nt-agent-next" onClick={onData}><Database size={14} /> 检查数据 <ArrowRight size={14} /></button> : !view?.pending ? <button type="button" className="nt-agent-next" onClick={() => onNavigate?.('atlas')}><Orbit size={14} /> 检查方案 <ArrowRight size={14} /></button> : <button type="button" className="nt-agent-next" onClick={() => onNavigate?.('bench')}><Sparkles size={14} /> 继续本轮 <ArrowRight size={14} /></button>}
      </section>
      <div className="nt-assistant-modes" role="tablist" aria-label="解释类型">
        {MODES.map(item => { const Icon = item.icon; return <button type="button" role="tab" aria-selected={action === item.id} className={action === item.id ? 'is-selected' : ''} key={item.id} onClick={() => setAction(item.id)}><Icon size={15} /><span>{item.label}</span></button> })}
      </div>
      <section className="nt-assistant-context">
        <span className="nt-kicker">CURRENT SCOPE</span>
        <strong>{current.label}</strong>
        <p>{current.hint}</p>
        <dl><div><dt>项目</dt><dd>{projectId || '— 未创建'}</dd></div>{action === 'candidate' && <div><dt>方案</dt><dd>{selectedCandidate?.row_id || '— 未选择'}</dd></div>}<div><dt>记录</dt><dd>{view?.snapshot ? `${view.snapshot.revealed_count} 次已公布` : '尚无项目'}</dd></div></dl>
      </section>
      {!projectId && <div className="nt-assistant-stop"><ShieldCheck size={16} /><div><strong>先创建项目</strong><p>助手不会读取方案标签或自行创建项目。</p></div></div>}
      {projectId && action === 'candidate' && !candidateReady && <div className="nt-assistant-stop"><ShieldCheck size={16} /><div><strong>先选方案</strong><p>从方案空间选择一条后，才可解释其公开字段。</p></div></div>}
      <label className="nt-assistant-question">问题（可选）<textarea value={question} maxLength={500} onChange={event => setQuestion(event.target.value)} placeholder={action === 'candidate' ? '例如：这条方案的差异代表什么？' : action === 'evidence' ? '例如：已公布记录能说明什么？' : '例如：答辩时应如何说明边界？'} /></label>
      <div className="nt-assistant-prompts">{QUICK_QUESTIONS[action].map(item => <button type="button" key={item} onClick={() => setQuestion(item)}>{item}</button>)}</div>
      <div className="nt-assistant-actions"><span>{question.length} / 500</span><button type="button" className="nt-primary" disabled={!canAsk} onClick={ask}>{state === 'loading' ? <><LoaderCircle size={15} className="nt-spin" /> 解释中</> : <><Send size={15} /> 请求解释</>}</button></div>
      {state === 'unconfigured' && <div className="nt-assistant-unconfigured"><BotMessageSquare size={17} /><div><strong>助手未配置</strong><p>{message || '未发送网络请求。配置 API Key 后才可使用。'}</p></div></div>}
      {state === 'error' && <div className="nt-assistant-error"><BotMessageSquare size={17} /><div><strong>解释未返回</strong><p>{message}</p></div></div>}
      {answer && <article className="nt-assistant-answer"><header><span>AI EXPLANATION</span><small>{answer.provider} · {answer.model}</small></header><p>{answer.answer}</p><footer><span><ShieldCheck size={13} /> {answer.disclaimer}</span><button type="button" className="nt-link-button" onClick={() => navigator.clipboard?.writeText(answer.answer)}><Clipboard size={12} /> 复制</button></footer></article>}
      <footer className="nt-assistant-boundary">不发送 pending target、独立留出标签、原始 CSV、文件路径或环境变量。</footer>
    </aside>
  </div>
}
