import React, { useEffect, useRef } from 'react'
import { ArrowRight, Database, Eye, LockKeyhole, Orbit } from 'lucide-react'
import { useDataset } from './dataset'

const STEPS = [
  ['01', '看数据', '先认识当前数据描述什么、目标是什么，以及已经有多少条实验记录。', '回到数据概览', 'mission', Database],
  ['02', '比方案', '比较配方、预测值和模型分歧。模型分歧只表示模型意见不一致，不是置信度。', '打开方案', 'atlas', Orbit],
  ['03', '锁预测', '选择策略、目标和查看次数，保存当前预测。保存后不能根据答案反向修改。', '进入实验', 'bench', LockKeyhole],
  ['04', '看结果', '打开一条过去已经完成的实验记录，对照预测、结果和误差，完成本轮。', '查看本轮证据', 'trail', Eye],
]

const TERMS = [
  ['历史回放', '用过去的实验，模拟一次“选方案—看结果—再学习”。'],
  ['模型分歧', '多个模型对同一方案意见有多不一致；不是概率或风险。'],
  ['锁定预测', '先把预测保存下来，之后不能根据结果修改。'],
  ['查看次数', '本轮最多打开几条历史结果，不是真实实验次数。'],
]

export default function GuideDrawer({ open, onClose, onNavigate }) {
  const meta = useDataset()
  const closeRef = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onKey = event => {
      if (event.key === 'Escape') onClose()
    }
    const timer = window.setTimeout(() => closeRef.current?.focus(), 30)
    window.addEventListener('keydown', onKey)
    return () => { window.clearTimeout(timer); window.removeEventListener('keydown', onKey) }
  }, [open, onClose])
  if (!open) return null
  return <div className="nt-guide-layer" role="dialog" aria-modal="true" aria-labelledby="nt-guide-title">
    <button type="button" className="nt-guide-backdrop" aria-label="关闭使用方法" onClick={onClose} />
    <aside className="nt-guide-drawer">
      <header className="nt-guide-head">
        <div><span className="nt-kicker">QUICK START / NEXTEST</span><h2 id="nt-guide-title">四步完成一次<br />历史实验回放</h2></div>
        <button ref={closeRef} type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭使用方法">×</button>
      </header>
      <p className="nt-guide-lead">NextTest 用已有实验数据，帮助你选择下一组值得验证的方案。先锁定模型预测，再查看一条历史结果，观察证据如何改变下一步。</p>
      <div className="nt-guide-steps">
        {STEPS.map(([index, title, detail, action, target, Icon]) => <article className="nt-guide-step" key={index}>
          <span className="nt-guide-index">{index}</span>
          <span className="nt-guide-icon"><Icon size={18} /></span>
          <div><strong>{title}</strong><p>{detail}</p>
            <button type="button" className="nt-link-button" onClick={() => { onClose(); onNavigate(target) }}>{action}<ArrowRight size={13} /></button>
          </div>
        </article>)}
      </div>
      <div className="nt-guide-terms" aria-label="常用术语白话解释">
        <strong>四个常用词</strong>
        <dl>{TERMS.map(([term, meaning]) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl>
      </div>
      <div className="nt-guide-boundary">
        <strong>当前版本的边界</strong>
        <span>✓ 当前数据集的历史回放</span>
        <span>✓ 三种选择方法 · 预测先保存 · 记录可核验</span>
        <span>✓ 可导入自己的 CSV 数据</span>
        <span>— 真实新实验录入：尚未开放</span>
      </div>
      <footer><span>ESC 关闭</span><span>所有计算均在本机完成</span></footer>
    </aside>
  </div>
}
