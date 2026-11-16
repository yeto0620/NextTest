import React, { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Bot, Eye, LockKeyhole, Orbit, Sparkles, X } from 'lucide-react'

const STEPS = [
  {
    icon: Sparkles,
    target: '[data-tour="nav"]',
    eyebrow: '01 / 这是做什么的',
    title: '从已有实验里，挑出下一组值得验证的方案',
    body: 'NextTest 不替你做真实实验。它用过去的数据模拟一次选择：先看推荐，再保存预测，最后查看一条历史结果。',
    action: '整个平台只有一条主线：看数据 → 比方案 → 锁预测 → 看结果。',
  },
  {
    icon: Orbit,
    target: '[data-tour="atlas"]',
    eyebrow: '02 / 比方案',
    title: '先比较推荐，不提前看答案',
    body: '方案页展示配方、预测值和模型分歧。模型分歧只表示多个模型意见不一致，不是风险、概率或置信度。',
    action: '系统预览只帮助比较；真正的决定从“锁定预测”开始。',
  },
  {
    icon: LockKeyhole,
    target: '[data-tour="bench"]',
    eyebrow: '03 / 锁预测',
    title: '先保存预测，再看历史结果',
    body: '锁定后，平台会保存当前方案和预测，不能根据答案反向修改。预算表示本轮最多查看几条历史记录，不是真实实验次数。',
    action: '锁定预测和查看结果是两个独立动作。',
  },
  {
    icon: Eye,
    target: '[data-tour="bench"]',
    eyebrow: '04 / 看结果',
    title: '查看一条结果，完成一轮回放',
    body: '平台依次展示封存预测、历史结果、误差和模型更新。看到“本轮完成”后，你可以结束并看总结，或继续下一轮。',
    action: '单条结果只说明这一条记录，不证明某种策略整体更好。',
  },
  {
    icon: Bot,
    target: '[data-tour="assistant"]',
    eyebrow: '05 / 随时求助',
    title: '术语不懂，就打开助手',
    body: '没有 DeepSeek Key 时，本地帮助仍可解释流程和下一步；配置 Key 后，助手可以解释当前项目的公开证据。',
    action: '助手不参与推荐，也不能读取隐藏结果。现在可以开始第一次回放。',
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
      <div className="nt-tour-foot">关闭后点击左侧“帮助”，可以重新查看引导</div>
    </div>
  </div>
}
