import React, { useEffect, useRef } from 'react'
import { ArrowRight, Beaker, Database, Download, GitBranch, LockKeyhole, Radar } from 'lucide-react'
import { useDataset } from './dataset'

const STEPS = [
  ['01', '准备数据', '确认来源、目标列、可控制变量和潜在泄漏。单位由用户声明，未经自动验证。', '查看数据契约', 'mission', Database],
  ['02', '观察空间', '在航图中寻找已知区域、空白区域和仍未被验证的材料配方。', '打开可能性航图', 'atlas', Radar],
  ['03', '比较策略', '切换预测优先、差异优先和随机对照，先看它们为什么指向不同方案。', '进入下一实验台', 'bench', Beaker],
  ['04', '锁定预测', '在公布结果前保存方案与预测。锁定后，历史实测仍然保持隐藏。', '锁定下一次实验', 'bench', LockKeyhole],
  ['05', '公布证据', '人工确认后才释放这一条历史实测，并把新记录追加到训练集。', '查看证据河流', 'trail', GitBranch],
  ['06', '导出证据', '导出可复核的记录；不是保存一张截图，也不把回放说成新实验。', '导出或核查', 'trail', Download],
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
        <div><span className="nt-kicker">OPERATION MAP / NEXTEST</span><h2 id="nt-guide-title">六步走完一次<br />历史实验回放</h2></div>
        <button ref={closeRef} type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭使用方法">×</button>
      </header>
      <p className="nt-guide-lead">这不是自动替你做实验。它帮助你在有限预算下决定下一条值得验证的历史方案，并把“预测”和“已经发生的结果”分开保存。</p>
      <div className="nt-guide-steps">
        {STEPS.map(([index, title, detail, action, target, Icon]) => <article className="nt-guide-step" key={index}>
          <span className="nt-guide-index">{index}</span>
          <span className="nt-guide-icon"><Icon size={18} /></span>
          <div><strong>{title}</strong><p>{detail}</p>
            <button type="button" className="nt-link-button" onClick={() => { onClose(); onNavigate(target) }}>{action}<ArrowRight size={13} /></button>
          </div>
        </article>)}
      </div>
      <div className="nt-guide-boundary">
        <strong>当前版本的边界</strong>
        <span>✓ 当前数据集的完整历史回放</span>
        <span>✓ 三种策略 · 预测先保存 · 事件可核验</span>
        <span>✓ 自定义 CSV：Data Dock</span>
        <span>— 真实新实验录入：尚未开放</span>
      </div>
      <footer><span>ESC 关闭</span><span>所有计算均在本机完成</span></footer>
    </aside>
  </div>
}
