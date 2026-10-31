import React from 'react'
import { ArrowRight, BookOpen, GitBranch, Lightbulb, Ruler } from 'lucide-react'
import { number } from './data'
import { useDataset } from './dataset'

function Scene({ code, title, one, children, concept, action, onFocus }) {
  return <article className={`nt-scene ${concept ? 'is-concept' : 'is-live'}`}>
    <header><span className="nt-scene-code">{code}</span><span className={`nt-scene-tag ${concept ? 'is-concept' : ''}`}>{concept ? '概念说明，非本轮数据' : '当前项目真实数据'}</span></header>
    <h3>{title}</h3><p>{one}</p>
    <div className="nt-scene-body">{children}</div>
    <button type="button" className="nt-link-button" onClick={() => onFocus(action)}><BookOpen size={12} /> 查看方法 <ArrowRight size={12} /></button>
  </article>
}

export default function ScienceScenes({ view, preview, pending, last, transition, onFocus }) {
  const meta = useDataset()
  const unit = meta.target.unit || ''
  const greedy = preview?.rankings?.greedy_prediction
  const disagreement = preview?.rankings?.max_disagreement
  const e1Real = Boolean(last)
  const e2Real = Boolean(view && greedy && disagreement)
  const e3Real = Boolean(transition?.before && transition?.after)
  return <section className="nt-scenes" id="scenes" aria-labelledby="nt-scenes-title">
    <header className="nt-section-head"><div><span className="nt-kicker">E1—E3 / SCIENCE SCENES</span><h2 id="nt-scenes-title">三个最容易混淆的问题</h2><p>每张场景都绑定当前项目或当前候选的真实字段；没有真实例子时明确标为概念说明。</p></div><Lightbulb size={22} /></header>
    <div className="nt-scenes-grid">
      <Scene code="E1" title="预测不是测量" one="模型先给出估计，真实结果要等揭示后才知道。" concept={!e1Real && !pending} action="seal" onFocus={onFocus}>
        {last ? <><b>{number(last.prediction, 2)} {unit}</b><span>预测 → </span><b>{number(last.revealed_target, 2)} {unit}</b><span>历史实测；差 {number(last.absolute_error, 2)} {unit}。</span></> : pending ? <><b>{number(pending.prediction, 2)} {unit}</b><span>是当前封存预测；历史实测仍未揭示。</span></> : <span>预测和实测是两种不同的事实层级。</span>}
      </Scene>
      <Scene code="E2" title="最高预测 ≠ 最值得测" one="追最高预测可能只重复模型已经熟悉的方向；测分歧更大的点可能得到更多信息。" concept={!e2Real} action="compare" onFocus={onFocus}>
        {e2Real ? <><span><Ruler size={12} /> 最高预测：{greedy.row_id} · {number(greedy.prediction, 2)} {unit}</span><span><GitBranch size={12} /> 最大分歧：{disagreement.row_id} · 分歧 {number(disagreement.disagreement, 2)} {unit}</span></> : <span>需要当前候选投影中的 prediction / disagreement 才能展示真实对照。</span>}
      </Scene>
      <Scene code="E3" title="证据改变判断" one="reveal 后，训练行、预算和模型版本会变化；系统不会偷偷改写历史。" concept={!e3Real} action="update" onFocus={onFocus}>
        {e3Real ? <><span>模型：{String(transition.before.model_sha).slice(0, 10)}… → {String(transition.after.model_sha).slice(0, 10)}…</span><span>训练：{transition.before.observed_count} → {transition.after.observed_count} 行；预算：{transition.before.remaining_budget} → {transition.after.remaining_budget} 次</span></> : <span>只有真实 reveal 完成后，才能显示前后模型与预算变化。</span>}
      </Scene>
    </div>
  </section>
}
