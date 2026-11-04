import React from 'react'
import { ArrowRight, Beaker, BookOpen, GitBranch, ShieldCheck } from 'lucide-react'
import { hypothesisLabel, number, reflectionDirection, reflectionSentence } from './data'
import { useDataset } from './dataset'

export default function ReflectionCard({ last, hypothesis, transition, onNavigate, onResearch }) {
  const meta = useDataset()
  const unit = meta.target.unit || 'unit not supplied'
  if (!last) return null
  const direction = reflectionDirection(last.prediction, last.revealed_target)
  const hypothesisText = hypothesis == null ? '未随项目保存' : hypothesisLabel(hypothesis)
  return <section className="nt-reflection" aria-labelledby="nt-reflection-title" aria-live="polite">
    <header><span className="nt-kicker">REFLECTION CARD / 单次结果，不是策略结论</span><h3 id="nt-reflection-title">{reflectionSentence(last.prediction, last.revealed_target)}</h3><span className={`nt-reflection-mark is-${direction}`}>{direction === 'higher' ? '实测高于预测' : direction === 'lower' ? '实测低于预测' : '两者接近'}</span></header>
    <div className="nt-reflection-grid">
      <div><span>我的预判</span><strong>{hypothesisText}</strong><small>{hypothesis?.note ? `“${hypothesis.note}”` : '预判只作个人反思，不改变模型。'}</small></div>
      <div><span>保存预测</span><strong>{number(last.prediction, 2)} <em>{unit}</em></strong></div>
      <div><span>历史实测</span><strong>{number(last.revealed_target, 2)} <em>{unit}</em></strong></div>
      <div><span>绝对误差</span><strong>{number(last.absolute_error, 2)} <em>{unit}</em></strong></div>
      <div><span>模型是否更新</span><strong>{transition?.before?.model_sha && transition?.after?.model_sha && transition.before.model_sha !== transition.after.model_sha ? '是，版本已变化' : transition ? '版本未变化' : '—'}</strong><small>{transition ? `${String(transition.before.model_sha).slice(0, 8)}… → ${String(transition.after.model_sha).slice(0, 8)}…` : '前后模型记录不可用'}</small></div>
      <div><span>训练行 / 预算</span><strong>{transition ? `${transition.after.observed_count} 行 / ${transition.after.remaining_budget} 次` : '—'}</strong><small>{transition ? `公布前 ${transition.before.observed_count} 行 / ${transition.before.remaining_budget} 次` : '没有可用的前后事实'}</small></div>
    </div>
    <p className="nt-reflection-boundary"><ShieldCheck size={13} /> 这是单次历史回放，只说明这一条记录，不证明策略整体更优；预测不是实测，预测差值异也不是概率或置信区间。</p>
    <div className="nt-reflection-actions">
      <button type="button" className="nt-primary" onClick={() => onNavigate('trail')}>查看证据如何进入下一轮 <ArrowRight size={15} /></button>
      <button type="button" className="nt-secondary-button" onClick={() => onNavigate('atlas')}><GitBranch size={14} /> 回到可能性航图</button>
      <button type="button" className="nt-link-button" onClick={onResearch}><BookOpen size={13} /> 展开方法细节</button>
      <span><Beaker size={12} /> 历史回放 / 非新实验</span>
    </div>
  </section>
}
