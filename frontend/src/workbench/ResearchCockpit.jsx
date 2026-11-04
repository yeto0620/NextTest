import React from 'react'
import {
  Archive, ArrowRight, Beaker, Bot, Database, GitCompareArrows,
  History, LockKeyhole, Orbit, Radar, RotateCcw, ShieldCheck,
} from 'lucide-react'
import ObservationPlate from './ObservationPlate'
import { number, statusLabel, strategyLabel } from './data'
import { useDataset } from './dataset'

const MODULES = [
  { id: 'atlas', label: '方案域', detail: '筛选与双方案对比', icon: Orbit },
  { id: 'bench', label: '实验台', detail: '保存预测并公布结果', icon: Beaker },
  { id: 'strategy', label: '策略场', detail: '固定协议描述性比较', icon: GitCompareArrows },
  { id: 'trail', label: '证据链', detail: '事件、SHA 与科研边界', icon: Radar },
]

export default function ResearchCockpit({
  landscape, preview, view, strategy, selectedCandidate, compareCandidate,
  selection, onSelectObserved, onNavigate, onStrategy, onLibrary, onData,
  onAssistant, resumeId, setResumeId, onResume, busy,
}) {
  const meta = useDataset()
  const snapshot = view?.snapshot
  const candidateCount = snapshot?.candidate_count ?? preview?.candidate_count
  const revealed = snapshot?.revealed_count ?? 0
  const budget = snapshot?.budget ?? 0
  const projectStatus = snapshot ? statusLabel(snapshot.status) : '待创建'
  const selectedPrediction = selectedCandidate?.prediction
  const selectedDisagreement = selectedCandidate?.disagreement

  return <section className="nt-research-cockpit" id="mission" aria-labelledby="nt-cockpit-title">
    <header className="nt-cockpit-head">
      <div>
        <span className="nt-kicker">RESEARCH CONSOLE / HISTORICAL REPLAY</span>
        <h1 id="nt-cockpit-title">实验控制台</h1>
      </div>
      <div className="nt-cockpit-headline">
        <span><i className="is-live" /> 数据就绪</span>
        <span><i className={snapshot ? 'is-live' : ''} /> {projectStatus}</span>
        <code>{meta.shortId || meta.id}</code>
      </div>
    </header>

    <div className="nt-cockpit-main">
      <div className="nt-cockpit-visual">
        <ObservationPlate mode="research" landscape={landscape} selectedCandidate={selectedCandidate}
          compareCandidate={compareCandidate} selection={selection} onSelectObserved={onSelectObserved} />
        <div className="nt-cockpit-signal" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
      </div>

      <aside className="nt-cockpit-rail" aria-label="当前实验状态">
        <div className="nt-cockpit-rail-head">
          <span className="nt-kicker">ACTIVE STUDY</span>
          <ShieldCheck size={15} />
        </div>
        <div className="nt-cockpit-study">
          <small>当前策略</small>
          <strong>{strategyLabel(snapshot?.strategy || strategy)}</strong>
          <span>{snapshot ? projectStatus : '尚未冻结实验项目'}</span>
        </div>
        <dl className="nt-cockpit-metrics">
          <div><dt>观测</dt><dd>{landscape?.rows?.length ?? '—'}</dd><small>train rows</small></div>
          <div><dt>方案</dt><dd>{candidateCount ?? '—'}</dd><small>target hidden</small></div>
          <div><dt>公布</dt><dd>{snapshot ? `${revealed}/${budget}` : '—'}</dd><small>historical replay</small></div>
          <div><dt>审计</dt><dd>{snapshot?.test_count ? 'PASS' : '—'}</dd><small>read only</small></div>
        </dl>

        <div className="nt-cockpit-selection">
          <div><span className="nt-kicker">SELECTED CANDIDATE</span><LockKeyhole size={13} /></div>
          <strong>{selectedCandidate?.row_id || '—'}</strong>
          <dl>
            <div><dt>预测</dt><dd>{number(selectedPrediction, 2)} <em>{meta.target.unit || ''}</em></dd></div>
            <div><dt>差异</dt><dd>{number(selectedDisagreement, 2)}</dd></div>
          </dl>
          <small>历史实测标签在公布前不进入浏览器</small>
        </div>

        <button type="button" className="nt-primary nt-cockpit-primary" onClick={() => onNavigate('bench')}>
          进入实验台 <ArrowRight size={15} />
        </button>
        <button type="button" className="nt-cockpit-strategy" onClick={onStrategy}>
          <GitCompareArrows size={14} /> 策略观测 <span>3 strategies</span>
        </button>
      </aside>
    </div>

    <div className="nt-cockpit-modules" aria-label="研究模块">
      {MODULES.map(module => {
        const Icon = module.icon
        return <button type="button" key={module.id} onClick={() => module.id === 'strategy' ? onStrategy() : onNavigate(module.id)}>
          <span><Icon size={16} /></span><strong>{module.label}</strong><small>{module.detail}</small><ArrowRight size={13} />
        </button>
      })}
      <button type="button" onClick={onLibrary}><span><Archive size={16} /></span><strong>项目库</strong><small>证据包与项目比较</small><ArrowRight size={13} /></button>
      <button type="button" onClick={onData}><span><Database size={16} /></span><strong>数据坞</strong><small>字段角色与数据闸门</small><ArrowRight size={13} /></button>
      <button type="button" onClick={onAssistant}><span><Bot size={16} /></span><strong>AI 助手</strong><small>任务链与受限证据解释</small><ArrowRight size={13} /></button>
    </div>

    <footer className="nt-cockpit-footer">
      <div><ShieldCheck size={13} /> 历史回放 ≠ 新物理实验 · 模型预测 ≠ 实测</div>
      <form onSubmit={event => { event.preventDefault(); onResume(resumeId.trim()) }}>
        <RotateCcw size={13} /><label htmlFor="nt-research-resume">只读恢复</label>
        <input id="nt-research-resume" value={resumeId} onChange={event => setResumeId(event.target.value)} placeholder="p2_ / p3_ 项目编号" />
        <button type="submit" disabled={busy || !resumeId.trim()}>打开</button>
      </form>
      {snapshot && <span><History size={13} /> {snapshot.project_id}</span>}
    </footer>
  </section>
}
