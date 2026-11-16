import React, { useState } from 'react'
import { HelpCircle, Sparkles } from 'lucide-react'
import { number, strategyLabel } from './data'
import { useDataset } from './dataset'

export default function QuestionRibbon({ view, strategy }) {
  const meta = useDataset()
  const [open, setOpen] = useState(false)
  const snapshot = view?.snapshot
  const pending = view?.pending
  const latest = view?.history?.at(-1)
  let label = '本轮问题'
  let question = '先看哪条历史实验？模型预测最强的，还是模型意见最不一致的？'
  if (snapshot && pending) {
    label = '问题已进入证据阶段'
    question = '预测已经保存。现在才允许查看历史实测。'
  } else if (snapshot && latest) {
    label = '证据之后'
    question = '这条证据让模型判断发生了什么变化？'
  } else if (snapshot && snapshot.status === 'ready') {
    label = '本轮问题'
    question = `这轮按“${strategyLabel(snapshot.strategy)}”选方案。为什么先看这一条？`
  }
  return <div className="nt-question-ribbon" data-state={pending ? 'pending' : latest ? 'revealed' : snapshot ? 'ready' : 'concept'}>
    <div className="nt-question-mark" aria-hidden="true"><Sparkles size={14} /></div>
    <div className="nt-question-copy"><span>{label}</span><strong>{question}</strong></div>
    <div className="nt-question-side">
      {snapshot && <span className="nt-question-fact">{snapshot.revealed_count}/{snapshot.budget} 已查看{latest ? ` · 最近 ${number(latest.absolute_error, 2)} ${meta.target.unit || ''} 误差` : ''}</span>}
      <button type="button" className="nt-question-toggle" aria-expanded={open} onClick={() => setOpen(value => !value)}><HelpCircle size={13} /> 为什么这是一个问题？</button>
    </div>
    {open && <div className="nt-question-explain" role="region" aria-label="问题解释">
      <p><b>预测不是测量。</b>模型只是根据已有历史记录给出估计；真实结果还没被读取。</p>
      <p><b>“最高预测”不等于“最值得测”。</b>它可能只是模型最熟悉的方向；验证一个模型分歧更大的点，可能得到更多信息。</p>
      <p><b>先保存判断，再查看。</b>这样新证据才能真实地改变下一轮建议，而不是事后改故事。</p>
    </div>}
  </div>
}
