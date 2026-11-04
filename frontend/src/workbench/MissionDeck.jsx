import React from 'react'
import { ArrowRight, CircleHelp, Database, History, LockKeyhole, Play, Radar, RotateCcw, ShieldCheck } from 'lucide-react'
import ObservationPlate from './ObservationPlate'
import QuestionRibbon from './QuestionRibbon'
import { statusLabel, strategyLabel } from './data'
import { useDataset } from './dataset'

export default function MissionDeck({ landscape, preview, view, strategy, selectedCandidate, compareCandidate, selection, onSelectObserved, onNavigate, onGuide, resumeId, setResumeId, onResume, busy, mode }) {
  const snapshot = view?.snapshot
  const meta = useDataset()
  const contextNames = meta.features.filter(f => f.role === 'context').map(f => f.displayName)
  const research = mode === 'research'
  return <section className="nt-mission-deck" id="mission" aria-labelledby="nt-mission-title">
    <div className="nt-mission-copy">
      <div className="nt-mission-eyebrow"><span className="nt-signal" /> {research ? 'OBSERVATION / REPLAY' : 'NEXTTEST / EXPERIMENT OBSERVATORY'} <span>HISTORICAL REPLAY</span></div>
      <h1 id="nt-mission-title">{research ? '观测' : <>下一次，<br /><span>先验证哪一组？</span></>}</h1>
      {!research && <p className="nt-mission-lead">把有限的实验预算，投向最值得验证的一步。<br />先保存预测，再公布历史结果，让证据改变下一次判断。</p>}
      {!research && <QuestionRibbon view={view} strategy={strategy} />}
      <div className="nt-mission-actions">
        <button type="button" className="nt-primary" onClick={() => onNavigate('bench')} aria-label="进入实验台"><Play size={15} fill="currentColor" /> {research ? '实验' : '开始下一次实验'} <ArrowRight size={15} /></button>
        <button type="button" className="nt-secondary-button" onClick={() => onNavigate('atlas')} aria-label="查看方案空间"><Radar size={15} /> {research ? '方案' : '查看方案'}</button>
        <button type="button" className="nt-link-button" onClick={onGuide} aria-label="打开使用方法"><CircleHelp size={14} /> {research ? '指南' : '使用方法'}</button>
      </div>
      <div className="nt-mission-boundary"><ShieldCheck size={13} /> 关联投影不等于因果 · 历史回放不等于新实验</div>
    </div>
    <ObservationPlate landscape={landscape} selectedCandidate={selectedCandidate} compareCandidate={compareCandidate} selection={selection} onSelectObserved={onSelectObserved} />
    <div className="nt-mission-facts">
      <div><span><Database size={14} /> {research ? '观测' : '已知记录'}</span><strong>{landscape?.rows?.length ?? '—'}</strong><small>{research ? '训练实测' : `条训练实测 · ${contextNames.join(' / ') || `${meta.features.length} 个特征`}`}</small></div>
      <div><span><LockKeyhole size={14} /> {research ? '方案' : '未公布方案'}</span><strong>{snapshot?.candidate_count ?? preview?.candidate_count ?? '—'}</strong><small>{research ? '标签隔离' : '历史结果不进入浏览器'}</small></div>
      <div><span><History size={14} /> {research ? '回放' : '当前回放'}</span><strong>{snapshot ? `${snapshot.revealed_count} / ${snapshot.budget}` : '—'}</strong><small>{snapshot ? statusLabel(snapshot.status) : '尚未创建项目'}</small></div>
      <button type="button" className="nt-fact-action" onClick={() => onNavigate('trail')}><ShieldCheck size={14} /><span>{research ? '证据' : '证据状态'}</span><strong>{snapshot ? (snapshot.test_count ? '可核验' : '—') : '—'}</strong><small>{research ? '事件链' : <>查看事件与边界 <ArrowRight size={12} /></>}</small></button>
    </div>
    <div className="nt-mission-recovery">
      <div><RotateCcw size={14} /><strong>{research ? '恢复' : '继续已有项目'}</strong><span>{research ? '只读' : '刷新后只读恢复，不重做计算。'}</span></div>
      <form onSubmit={event => { event.preventDefault(); onResume(resumeId.trim()) }}>
        <input value={resumeId} onChange={event => setResumeId(event.target.value)} placeholder="p2_ 后接 32 位编号" aria-label="项目编号" />
        <button type="submit" className="nt-secondary-button" disabled={busy || !resumeId.trim()}>打开项目 <ArrowRight size={13} /></button>
      </form>
      {snapshot && <span className="nt-recovery-current">当前：{snapshot.project_id} · {strategyLabel(snapshot.strategy)}</span>}
    </div>
  </section>
}
