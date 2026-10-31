import React, { useEffect, useState } from 'react'
import { ArrowRight, Compass, Database, FlaskConical, Sparkles, X } from 'lucide-react'

const STEPS = [
  {
    icon: Compass,
    target: '[data-tour="nav"]',
    eyebrow: '01 / 研究模式',
    title: '先看已知，再选下一次',
    body: '从观测、候选、实验进入。研究模式把候选表格、预测、模型分歧和审计信息放在同一屏。',
  },
  {
    icon: FlaskConical,
    target: '[data-tour="bench"]',
    eyebrow: '02 / 实验台',
    title: '先封存，后揭示',
    body: '选择候选后先锁定预测；人工确认，系统才揭示一条历史实测，并更新模型与证据链。',
  },
  {
    icon: Database,
    target: '[data-tour="data"]',
    eyebrow: '03 / 数据与证据',
    title: '自己的数据也能进入同一流程',
    body: '数据坞检查字段、缺失和泄漏；策略观测台做固定种子对照；项目库和证据包保留每次判断。',
  },
  {
    icon: Sparkles,
    target: '[data-tour="mode"]',
    eyebrow: '04 / 研究 + 科普',
    title: '同一事实，两种讲法',
    body: '切换到科普模式看导览、航图、体验和故事。科研智能体只解释公开证据，不替你做科研决定。',
  },
]

export default function NewUserTour({ open, onClose }) {
  const [step, setStep] = useState(0)
  useEffect(() => {
    if (!open) return undefined
    const target = document.querySelector(STEPS[step].target)
    if (!target) return undefined
    target.classList.add('nt-tour-spotlight')
    target.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' })
    return () => target.classList.remove('nt-tour-spotlight')
  }, [open, step])
  if (!open) return null
  const item = STEPS[step]
  const Icon = item.icon
  const last = step === STEPS.length - 1
  return <div className="nt-tour-layer" role="dialog" aria-modal="true" aria-label="NextTest 新手引导">
    <div className="nt-tour-card">
      <button type="button" className="nt-tour-close" onClick={onClose} aria-label="关闭新手引导"><X size={16} /></button>
      <div className="nt-tour-icon"><Icon size={22} /></div>
      <div className="nt-tour-eyebrow">{item.eyebrow}</div>
      <h2>{item.title}</h2>
      <p>{item.body}</p>
      <div className="nt-tour-progress" aria-label={`第 ${step + 1} 步，共 ${STEPS.length} 步`}>
        {STEPS.map((_, i) => <i key={i} className={i === step ? 'is-active' : ''} />)}
      </div>
      <div className="nt-tour-actions">
        <button type="button" className="nt-tour-skip" onClick={onClose}>跳过，直接使用</button>
        <button type="button" className="nt-tour-next" onClick={() => last ? onClose() : setStep(step + 1)}>
          {last ? '开始使用' : '下一步'} <ArrowRight size={15} />
        </button>
      </div>
      <div className="nt-tour-foot">以后可从顶栏的 ✦ 重新打开</div>
    </div>
  </div>
}
