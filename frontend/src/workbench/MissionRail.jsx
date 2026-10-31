import React from 'react'
import { Activity, ArrowRight, CircleHelp, FlaskConical, GitBranch, Radar, ShieldCheck } from 'lucide-react'
import { useDataset } from './dataset'

const MISSIONS = [
  ['mission', 'A1', '任务甲板', '现在知道什么', Activity],
  ['atlas', 'A2', '可能性航图', '未知落在哪里', Radar],
  ['bench', 'B1', '下一实验台', '比较并锁定下一步', FlaskConical],
  ['trail', 'C1', '证据河流', '预测如何被改变', GitBranch],
]

export default function MissionRail({ active, onNavigate, onGuide, status, onDataset }) {
  const meta = useDataset()
  return <aside className="nt-rail" aria-label="NextTest 任务导航">
    <div className="nt-brand">
      <span className="nt-brand-mark"><Radar size={21} strokeWidth={1.6} /></span>
      <span><strong>NextTest</strong><small>EXPERIMENT OBSERVATORY</small></span>
    </div>
    <button type="button" className="nt-dataset-identity" onClick={onDataset} title="查看 Dataset Passport"><span className="nt-kicker">LOCAL DATASET</span><strong>{meta.displayName}</strong><small>{meta.shortId || '—'} · {meta.target.displayName}</small></button>
    <div className="nt-rail-kicker">MISSION RAIL <span>{meta.isCustom ? 'LOCAL DATASET' : 'DEMO DATASET'}</span></div>
    <nav className="nt-rail-nav">
      {MISSIONS.map(([id, code, title, detail, Icon]) => (
        <button key={id} type="button" className={`nt-mission ${active === id ? 'is-active' : ''}`}
          onClick={() => onNavigate(id)} aria-current={active === id ? 'page' : undefined}>
          <span className="nt-mission-code">{code}</span>
          <span className="nt-mission-icon"><Icon size={16} /></span>
          <span className="nt-mission-copy"><strong>{title}</strong><small>{detail}</small></span>
          <span className="nt-mission-tracer" aria-hidden="true" />
        </button>
      ))}
    </nav>
    <button type="button" className="nt-guide-trigger" onClick={onGuide}>
      <CircleHelp size={16} /><span><strong>第一次使用？</strong><small>打开六步操作图</small></span><ArrowRight size={14} />
    </button>
    <div className="nt-rail-status">
      <div><span className={`nt-signal ${status === 'stopped' ? 'is-danger' : ''}`} /> LOCAL INSTRUMENT</div>
      <p>{meta.isCustom ? '本地数据 · 历史回放' : '公开数据 · 历史回放'}</p>
      <p className="nt-rail-boundary"><ShieldCheck size={12} /> 预测不是实测 · 单位未验证</p>
    </div>
    <div className="nt-rail-foot">1280—1920 DESKTOP <span>NO CLOUD</span></div>
  </aside>
}
