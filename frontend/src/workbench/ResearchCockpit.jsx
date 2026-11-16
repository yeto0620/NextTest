import React, { useState } from 'react'
import { ArrowRight, ChevronDown, ShieldCheck } from 'lucide-react'
import ObservationPlate from './ObservationPlate'
import ObservationConstellation from './ObservationConstellation'
import { number } from './data'
import { useDataset } from './dataset'

export default function ResearchCockpit({
  landscape, view, selectedCandidate, compareCandidate,
  selection, onSelectObserved, onNavigate,
  resumeId, setResumeId, onResume, busy,
}) {
  const meta = useDataset()
  const [visualMode, setVisualMode] = useState('chart')
  const snapshot = view?.snapshot
  const pending = snapshot?.status === 'awaiting_user_confirmation'
  const revealed = snapshot?.revealed_count ?? 0
  const completed = revealed > 0 && snapshot?.status === 'ready'
  const ended = ['budget_exhausted', 'candidate_pool_empty'].includes(snapshot?.status)
  const stopped = ['release_uncertain', 'update_uncertain', 'update_failed', 'stopped'].includes(snapshot?.status)
  const currentStep = pending || stopped ? 2 : completed || ended ? 3 : 1
  const nextAction = pending ? '查看已锁预测' : ended ? '查看本次结果' : stopped ? '查看停止原因' : completed ? '继续下一轮' : '开始一次回放'
  const predicted = pending ? view?.pending?.prediction : selectedCandidate?.prediction
  const candidateId = pending ? view?.pending?.row_id : selectedCandidate?.row_id

  return <section className="nt-replay-home" id="mission" aria-labelledby="nt-replay-title">
    <div className="nt-replay-hero">
      <div className="nt-replay-intro">
        <h1 id="nt-replay-title">先看预测，<br /><em>再看答案。</em></h1>
        <button type="button" className="nt-replay-cta nt-head-action" onClick={() => onNavigate(ended ? 'trail' : 'bench')}>
          {nextAction}<ArrowRight size={20} />
        </button>
        <span className="nt-replay-under-cta">历史回放 · 非真实实验</span>
      </div>
      <div className="nt-replay-preview" aria-label="当前方案预览">
        <div className="nt-replay-preview-head"><span>本轮方案</span><strong>{candidateId || (ended ? '已结束' : '正在读取')}</strong></div>
        <div className="nt-replay-prediction"><span>模型预测 · {meta.target.displayName}</span><strong>{predicted == null ? '—' : number(predicted, 2)} <small>{predicted == null ? '' : meta.target.unit || ''}</small></strong></div>
        <div className="nt-replay-answer"><span>历史实测</span><strong>{pending ? '本条尚未揭晓' : revealed > 0 ? '最近结果见回放页' : '锁定后揭晓'}</strong><i /></div>
        <div className="nt-replay-preview-foot"><ShieldCheck size={15} /> {pending ? '已锁定 · 结果隐藏' : '仅预览 · 尚未锁定'}</div>
      </div>
    </div>
    <div className="nt-replay-path" aria-label="完成一次回放的步骤">
      {[
        ['1', '选方法'],
        ['2', '锁预测'],
        ['3', '看答案'],
      ].map(([step, title], index) => <button type="button" key={step}
        className={currentStep === index + 1 ? 'is-current' : ''}
        onClick={() => onNavigate(index === 2 && revealed > 0 ? 'trail' : 'bench')}>
        <b>{step}</b><span><strong>{title}</strong></span>
      </button>)}
    </div>
    <div className="nt-replay-lower">
      <button type="button" className="nt-replay-link" onClick={() => onNavigate('atlas')}>浏览全部方案 <ArrowRight size={14} /></button>
    </div>
    <details className="nt-replay-explore"><summary><span>数据预览</span><ChevronDown size={15} /></summary>
      <div className="nt-replay-view-toggle" role="group" aria-label="观测图视图">
        <button type="button" aria-pressed={visualMode === 'chart'} className={visualMode === 'chart' ? 'is-selected' : ''} onClick={() => setVisualMode('chart')}>二维图</button>
        <button type="button" aria-pressed={visualMode === 'constellation'} className={visualMode === 'constellation' ? 'is-selected' : ''} onClick={() => setVisualMode('constellation')}>星图</button>
      </div>
      <div className="nt-replay-observation">
        {visualMode === 'chart'
          ? <ObservationPlate mode="research" landscape={landscape} selectedCandidate={selectedCandidate} compareCandidate={compareCandidate} selection={selection} onSelectObserved={onSelectObserved} />
          : <ObservationConstellation landscape={landscape} selectedCandidate={selectedCandidate} compareCandidate={compareCandidate} selection={selection} onSelectObserved={onSelectObserved} />}
      </div>
      <p>图中的点来自已知训练记录。分布表示关联，不证明原因。</p>
    </details>
    <details className="nt-cockpit-more nt-replay-more"><summary><span>恢复项目</span><ChevronDown size={15} /></summary>
      <form className="nt-replay-resume" onSubmit={event => { event.preventDefault(); onResume(resumeId.trim()) }}>
        <label htmlFor="nt-research-resume">继续旧项目</label>
        <input id="nt-research-resume" value={resumeId} onChange={event => setResumeId(event.target.value)} placeholder="粘贴项目编号" />
        <button type="submit" disabled={busy || !resumeId.trim()}>打开</button>
      </form>
    </details>
  </section>
}
