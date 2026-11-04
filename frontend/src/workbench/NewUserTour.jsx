import React, { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Bot, Compass, Database, FlaskConical, Orbit, ScanSearch, Sparkles, X } from 'lucide-react'

const STEPS = [
  {
    icon: Compass,
    target: '[data-tour="nav"]',
    eyebrow: '01 / 研究导航',
    title: '先看导航：七条研究路径',
    body: '观测、候选、实验、策略、证据、档案、数据。研究模式先看证据，再决定下一次；每个入口对应一个明确任务。',
    action: '高亮的是导航；点任意入口切换工作区。',
  },
  {
    icon: Orbit,
    target: '[data-tour="atlas"]',
    eyebrow: '02 / 候选',
    title: '候选：先比较，不读答案',
    body: '候选页只展示配方、预测和模型分歧；历史实测标签在你锁定并确认揭示前不会出现。',
    action: '先看候选，不要急着找“正确答案”。',
  },
  {
    icon: FlaskConical,
    target: '[data-tour="bench"]',
    eyebrow: '03 / 实验台',
    title: '实验：先封存，后揭示',
    body: '选择策略、目标和预算，锁定当前预测；确认后只揭示一条历史实测，再更新模型与证据链。',
    action: '锁定和揭示是两个独立动作。',
  },
  {
    icon: Database,
    target: '[data-tour="data"]',
    eyebrow: '04 / 数据坞',
    title: '自己的数据先过闸门',
    body: '导入 CSV，确认字段角色、缺失、重复和泄漏风险；冻结只读数据护照后，才进入同一套候选与实验流程。',
    action: '原始文件只在本机处理，不进入模型上下文。',
  },
  {
    icon: Sparkles,
    target: '[data-tour="mode"]',
    eyebrow: '05 / 研究 + 科普',
    title: '同一事实，两种讲法',
    body: '研究模式看控制量、审计和 SHA；科普模式看导览、航图、体验和故事。两个模式共享候选与历史回放。',
    action: '切换模式时，导航、组件和信息密度一起变化。',
  },
  {
    icon: Bot,
    target: '[data-tour="assistant"]',
    eyebrow: '06 / 小精灵',
    title: '不懂就直接问',
    body: '点科研智能体或右下角小精灵，询问当前候选、模型分歧或页面含义。普通模式下入口置灰，选择 DeepSeek 模式后可用。',
    action: '没有 Key 时使用本地规则；有 Key 时解释公开证据。',
  },
  {
    icon: ScanSearch,
    target: '[data-tour="nav"]',
    eyebrow: '07 / 开始',
    title: '建议从“候选”或“实验”开始',
    body: '如果只想快速体验：观测 → 候选 → 实验 → 锁定 → 揭示。每一步都有 ? 和说明；需要完整操作表可打开桌面说明书。',
    action: '点击“开始使用”关闭引导，随时可按顶栏 ✦ 重开。',
  },
]

export default function NewUserTour({ open, onClose }) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (open) setStep(0)
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const target = document.querySelector(STEPS[step].target)
    if (!target) return undefined
    target.classList.add('nt-tour-spotlight')
    target.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' })
    return () => target.classList.remove('nt-tour-spotlight')
  }, [open, step])

  useEffect(() => {
    if (!open) return undefined
    const onKey = event => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowRight') setStep(current => Math.min(STEPS.length - 1, current + 1))
      if (event.key === 'ArrowLeft') setStep(current => Math.max(0, current - 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  const item = STEPS[step]
  const Icon = item.icon
  const last = step === STEPS.length - 1
  const next = () => last ? onClose() : setStep(current => Math.min(STEPS.length - 1, current + 1))
  const previous = () => setStep(current => Math.max(0, current - 1))

  return <div className="nt-tour-layer" role="dialog" aria-modal="true" aria-label="NextTest 新手引导">
    <div className="nt-tour-card">
      <button type="button" className="nt-tour-close" onClick={onClose} aria-label="关闭新手引导"><X size={16} /></button>
      <div className="nt-tour-topline">
        <span>{String(step + 1).padStart(2, '0')} / {String(STEPS.length).padStart(2, '0')}</span>
        <span>左右方向键翻页</span>
      </div>
      <div className="nt-tour-icon"><Icon size={22} /></div>
      <div className="nt-tour-eyebrow">{item.eyebrow}</div>
      <h2>{item.title}</h2>
      <p>{item.body}</p>
      <div className="nt-tour-action">{item.action}</div>
      <div className="nt-tour-progress" aria-label={`第 ${step + 1} 步，共 ${STEPS.length} 步`}>
        {STEPS.map((_, i) => <button type="button" key={i} className={i === step ? 'is-active' : ''} onClick={() => setStep(i)} aria-label={`跳到第 ${i + 1} 步`} />)}
      </div>
      <div className="nt-tour-actions">
        <button type="button" className="nt-tour-skip" onClick={onClose}>跳过，直接使用</button>
        <div className="nt-tour-nav">
          <button type="button" className="nt-tour-back" onClick={previous} disabled={step === 0}><ArrowLeft size={14} /> 上一步</button>
          <button type="button" className="nt-tour-next" onClick={next}>{last ? '开始使用' : '下一步'} <ArrowRight size={15} /></button>
        </div>
      </div>
      <div className="nt-tour-foot">关闭后再点顶栏 ✦，会从第 1 步重新开始</div>
    </div>
  </div>
}
