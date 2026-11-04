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
  let question = '如果实验预算有限，下一次测量应该追求最高预测，还是最大信息增量？'
  if (snapshot && pending) {
    label = '问题已进入证据阶段'
    question = '预测已经保存。现在才允许公布历史实测。'
  } else if (snapshot && latest) {
    label = '证据之后'
    question = '这条证据让模型判断发生了什么变化？'
  } else if (snapshot && snapshot.status === 'ready') {
    label = '本轮问题'
    question = `这一次，应该继续追“${strategyLabel(snapshot.strategy)}”最看好的方案，还是先测更不确定的方案？`
  }
  return <div className="nt-question-ribbon" data-state={pending ? 'pending' : latest ? 'revealed' : snapshot ? 'ready' : 'concept'}>
    <div className="nt-question-mark" aria-hidden="true"><Sparkles size={14} /></div>
    <div className="nt-question-copy"><span>{label}</span><strong>{question}</strong></div>
    <div className="nt-question-side">
      {snapshot && <span className="nt-question-fact">{snapshot.revealed_count}/{snapshot.budget} 已公布{latest ? ` · 最近 ${number(latest.absolute_error, 2)} ${meta.target.unit || ''} 误差` : ''}</span>}
      <button type="button" className="nt-question-toggle" aria-expanded={open} onClick={() => setOpen(value => !value)}><HelpCircle size={13} /> 为什么这是一个问题？</button>
    </div>
    {open && <div className="nt-question-explain" role="region" aria-label="问题解释">
      <p><b>预测不是测量。</b>模型只是根据已有历史记录给出估计；真实结果还没被读取。</p>
      <p><b>“最高预测”不等于“最值得测”。</b>它可能只是模型最熟悉的方向；测一个预测差值异更大的点，可能得到更多信息。</p>
      <p><b>先保存判断，再公布。</b>这样新证据才能真实地改变下一轮建议，而不是事后改故事。</p>
    </div>}
  </div>
}
