import React from 'react'
import { ArrowUpRight, CircleHelp, Crosshair } from 'lucide-react'
import { number, strategyLabel } from './data'
import { useDataset } from './dataset'

const LENSES = [
  {
    id: 'random',
    title: '随机抽取',
    one: '在不使用预测信息的条件下，随机挑一条方案。',
    sort: '按固定随机顺序抽取；不按预测值排序。',
    not: '不代表“没有信息”，也不能说明随机策略更差或更好。',
  },
  {
    id: 'greedy_prediction',
    title: '最高预测',
    one: '优先验证模型当前最看好的方案。',
    sort: '按模型预测值排序；目标为最大化时从高到低，最小化时从低到高；同分按 row ID。',
    not: '最高预测不等于实测最高，也不等于最值得测。',
  },
  {
    id: 'max_disagreement',
    title: '最大差异',
    one: '优先验证树模型意见最不一致的方案。',
    sort: '按 RandomForest 各棵树的预测标准差排序；同分按 row ID。',
    not: '预测差值异不是概率、置信度或统计不确定性保证。',
  },
]

export default function StrategyLens({ strategy, view, preview, pending, mode, onStrategy }) {
  const meta = useDataset()
  const research = mode === 'research'
  const active = view?.snapshot?.strategy || strategy
  const selected = preview?.selected?.row_id
  const current = preview?.rankings?.[active]
  return <div className="nt-strategy-lens" aria-label="策略透镜">
    <div className="nt-lens-head"><span className="nt-kicker">{research ? '策略' : 'STRATEGY LENS / 当前策略如何看方案'}</span>{!research && <span className="nt-lens-boundary"><Crosshair size={12} /> 只改变观察方式，不增加综合评分</span>}</div>
    <div className="nt-lens-grid">
      {LENSES.map((lens, index) => <button type="button" key={lens.id} className={`nt-lens ${active === lens.id ? 'is-active' : ''}`} onClick={() => !view && onStrategy?.(lens.id)} disabled={Boolean(view)} aria-pressed={active === lens.id}>
        <span className="nt-lens-index">L{index + 1}</span>
        <span className="nt-lens-copy"><strong>{lens.title}</strong>{!research && <small>{lens.one}</small>}</span>
        {active === lens.id && <span className="nt-lens-current">当前</span>}
      </button>)}
    </div>
    <div className="nt-lens-readout">
      <div><span>{research ? '排序' : '当前排序方式'}</span><strong>{LENSES.find(item => item.id === active)?.sort || '—'}</strong></div>
      <div><span>{research ? '边界' : '它不意味着'}</span><strong>{LENSES.find(item => item.id === active)?.not || '—'}</strong></div>
      <div><span>{research ? '本轮' : '当前方案为何在前'}</span><strong>{active === 'greedy_prediction' ? `预测 ${number(current?.prediction ?? pending?.prediction, 2)} ${meta.target.unit || ''}` : active === 'max_disagreement' ? `预测差值异 ${number(current?.disagreement ?? pending?.disagreement, 2)} ${meta.target.unit || ''}` : pending?.row_id ? `本轮固定随机抽到 ${pending.row_id}` : '随机对照不使用预测值'}{selected && active === strategy ? ` · ${selected}` : ''}</strong></div>
      {mode === 'research' && <div className="nt-lens-research"><span>可复核字段</span><code>prediction / disagreement / row_id / goal / strategy</code><span>排序字段</span><code>{active === 'greedy_prediction' ? 'prediction' : active === 'max_disagreement' ? 'tree std' : 'fixed rng'}</code></div>}
    </div>
    {!research && <footer><CircleHelp size={12} /><span>这些解释只描述当前排序规则，不比较三种策略谁更好。</span><span className="nt-lens-strategy">{strategyLabel(active)}</span></footer>}
  </div>
}
