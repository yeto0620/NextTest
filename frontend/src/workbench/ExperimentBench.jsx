import React from 'react'
import { ArrowRight, Beaker, Check, ChevronRight, Columns2, History, LockKeyhole, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react'
import { STRATEGY_META, controlEntries, number, statusLabel, strategyLabel } from './data'
import { useDataset, labelFor } from './dataset'
import HypothesisSlip from './HypothesisSlip'
import EvidencePrism from './EvidencePrism'
import ReflectionCard from './ReflectionCard'

function CandidateCard({ row, active, pending, compare, onSelect, onCompare, side, research }) {
  const meta = useDataset()
  if (!row) return <div className="nt-compare-card nt-compare-empty"><ShieldAlert size={16} /><strong>没有第二个候选</strong><p>后端没有返回可比较的候选；界面不会编造对照。</p></div>
  const prediction = pending ? pending.prediction : row.prediction
  const disagreement = pending ? pending.disagreement : row.disagreement
  const controls = pending ? pending.controls : row.controls
  return <article className={`nt-compare-card ${active ? 'is-active' : ''} ${pending ? 'is-pending' : ''}`} onClick={() => onSelect(row.row_id)}>
    <header><span className="nt-kicker">{side === 'A' ? 'CANDIDATE A' : 'CANDIDATE B'} / {row.row_id}</span><span className={`nt-state ${pending ? 'nt-state-pending' : 'nt-state-open'}`}>{pending ? '已锁定 · 未揭示' : '候选 · 未揭示'}</span></header>
    <div className="nt-compare-number"><span>预测 {meta.target.displayName}</span><strong>{number(prediction, 2)} <em>{meta.target.unit || 'unit not supplied'}</em></strong></div>
    <div className="nt-compare-facts"><div><span>模型分歧</span><strong>{disagreement == null ? '—' : `${number(disagreement, 2)} ${meta.target.unit || ''}`}</strong></div><div><span>历史实测</span><strong className="nt-missing">—</strong></div></div>
    <dl>{(research ? controlEntries(controls) : controlEntries(controls).slice(0, 4)).map(([key, value]) => <div key={key}><dt>{labelFor(meta, key)}</dt><dd>{number(value, 1)}</dd></div>)}</dl>
    <footer><button type="button" className="nt-link-button" onClick={event => { event.stopPropagation(); onCompare(row.row_id) }}><Columns2 size={12} /> {compare ? '已加入对比' : '加入对比'}</button><span>{pending ? '确认后释放' : '只读预览'}</span></footer>
  </article>
}

function HistoryOutcome({ item }) {
  const meta = useDataset()
  if (!item) return null
  return <div className="nt-outcome"><div><span>揭示前预测</span><strong>{number(item.prediction, 2)} <em>{meta.target.unit || ''}</em></strong></div><ArrowRight size={16} /><div><span>历史实测</span><strong>{number(item.revealed_target, 2)} <em>{meta.target.unit || ''}</em></strong></div><small>绝对误差 {number(item.absolute_error, 2)} {meta.target.unit || ''} · 单次差异不证明策略更优</small></div>
}

export default function ExperimentBench(props) {
  const meta = useDataset()
  const { preview, view, candidates, selectedId, compareIds, strategy, goal, threshold, budget, busy, mode,
    hypothesis, hypothesisLocal, reflectionHypothesis, onHypothesisChange, onHypothesisSkip, transition, onNavigate, onResearch,
    onSelect, onCompare, onStrategy, onGoal, onThreshold, onBudget, onLock, onReveal, onRecommend, onRefresh, onReset } = props
  const snapshot = view?.snapshot
  const research = mode === 'research'
  const pending = view?.pending
  const last = view?.history?.at(-1)
  const selected = candidates.find(row => row.row_id === selectedId) || null
  const compareRow = candidates.find(row => compareIds.includes(row.row_id) && row.row_id !== selectedId) || candidates.find(row => row.row_id !== selectedId) || null
  const lockedStrategy = snapshot?.strategy || strategy
  const canLock = !busy && Boolean(selected || pending)
  const isReady = !snapshot || snapshot.status === 'ready'
  return <section className="nt-bench" id="bench" aria-labelledby="nt-bench-title">
    <header className="nt-section-head">
      <div><span className="nt-kicker">{research ? '实验' : 'B1 / NEXT EXPERIMENT BENCH'}</span><h2 id="nt-bench-title">{research ? '实验' : '下一次，先验证哪一组？'}</h2>{!research && <p>比较两个真实候选，而不是看一个被包装过的答案。预测先封存，历史结果后揭示。</p>}</div>
      <div className="nt-bench-status"><span className={`nt-signal ${snapshot?.status && !['ready', 'awaiting_user_confirmation'].includes(snapshot.status) ? 'is-danger' : ''}`} />{snapshot ? statusLabel(snapshot.status) : '尚未锁定项目'}</div>
    </header>

    <div className="nt-console-sequence" aria-label="实验操作顺序">
      <span className="is-ready"><i />策略</span><b />
      <span className={selected || pending ? 'is-ready' : ''}><i />选择</span><b />
      <span className={snapshot?.status === 'awaiting_user_confirmation' || last ? 'is-ready' : ''}><i />封存</span><b />
      <span className={last ? 'is-ready' : ''}><i />揭示</span>
      <em>{research ? '只读回放' : '预测先于历史实测保存'}</em>
    </div>

    {research && <div className="nt-research-operation-strip" aria-label="研究运行参数">
      <div><span>项目</span><code>{snapshot?.project_id || 'unfrozen'}</code></div>
      <div><span>策略</span><code>{strategyLabel(lockedStrategy)}</code></div>
      <div><span>阈值</span><code>{threshold ?? '—'}</code></div>
      <div><span>模型</span><code>{(snapshot?.current_model_sha || preview?.model_sha || '—').slice(0, 12)}</code></div>
      <div><span>状态</span><code>{snapshot?.status || 'preview'}</code></div>
    </div>}

    {!research && (!snapshot || ['ready', 'awaiting_user_confirmation'].includes(snapshot.status)) && <HypothesisSlip hypothesis={hypothesis} onChange={onHypothesisChange} onSkip={onHypothesisSkip} locked={Boolean(snapshot)} nextRound={Boolean(last)} savedWithoutLocal={Boolean(snapshot?.status === 'awaiting_user_confirmation' && !hypothesisLocal)} />}
    <div className="nt-bench-grid">
      <div className="nt-bench-controls">
        <div className="nt-control-block">
          <div className="nt-control-title"><span>01</span><strong>策略</strong>{!research && <small>{snapshot ? '项目策略已锁定' : '锁定前可切换'}</small>}</div>
          <div className="nt-strategy-stack" role="group" aria-label="推荐策略">
            {Object.entries(STRATEGY_META).map(([id, meta]) => <button type="button" key={id} disabled={Boolean(snapshot)} className={strategy === id ? 'is-selected' : ''} onClick={() => onStrategy(id)}>
              <span><strong>{meta.label}</strong>{!research && <small>{meta.copy}</small>}</span><i className="nt-radio" />
            </button>)}
          </div>
          {snapshot && !research && <p className="nt-control-note">已锁定：{strategyLabel(snapshot.strategy)}。要换策略请新建项目；系统不会偷偷改已有记录。</p>}
        </div>

        <div className="nt-control-block">
          <div className="nt-control-title"><span>02</span><strong>目标</strong>{!research && <small>目标方向</small>}</div>
          <div className="nt-segmented full"><button type="button" className={goal === 'maximize' ? 'is-selected' : ''} disabled={Boolean(snapshot)} onClick={() => onGoal('maximize')}>尽量提高强度</button><button type="button" className={goal === 'minimize' ? 'is-selected' : ''} disabled={Boolean(snapshot)} onClick={() => onGoal('minimize')}>尽量降低目标</button></div>
          <label className="nt-threshold"><input type="checkbox" checked={threshold != null} disabled={Boolean(snapshot)} onChange={e => onThreshold(e.target.checked ? 40 : null)} /> 设置参考阈值（可选）</label>
          {threshold != null && <div className="nt-threshold-input"><input type="number" min="-1000000" max="1000000" step="0.1" value={threshold} disabled={Boolean(snapshot)} onChange={e => onThreshold(Number(e.target.value))} aria-label="参考阈值" /><span>{meta.target.unit || ''}</span></div>}
        </div>

        <div className="nt-control-block">
          <div className="nt-control-title"><span>03</span><strong>预算</strong>{!research && <small>{snapshot ? '已创建项目不可改' : '最多揭示几次历史结果'}</small>}</div>
          <div className="nt-budget-row"><input type="range" min="1" max="20" value={snapshot?.budget || budget} disabled={Boolean(snapshot)} onChange={e => onBudget(Number(e.target.value))} aria-label="回放预算" /><strong>{snapshot?.budget || budget} <small>次</small></strong></div>
          <div className="nt-range-ends"><span>1 次</span><span>20 次</span></div>
        </div>

        <div className="nt-bench-action">
          {!snapshot && <button type="button" className="nt-primary" disabled={!canLock} onClick={onLock}><LockKeyhole size={16} /> {busy ? '正在锁定…' : '锁定下一实验'}<ArrowRight size={16} /></button>}
          {snapshot?.status === 'ready' && <button type="button" className="nt-primary" disabled={busy} onClick={onRecommend}><LockKeyhole size={16} /> {busy ? '正在保存预测…' : '锁定下一实验'}<ArrowRight size={16} /></button>}
          {snapshot?.status === 'awaiting_user_confirmation' && <button type="button" className="nt-primary nt-primary-amber" disabled={busy} onClick={() => onReveal(pending.recommendation_id)}><Beaker size={16} /> {busy ? '正在揭示…' : '确认揭示历史实测'}<ArrowRight size={16} /></button>}
          {snapshot && <div className="nt-secondary-actions"><button type="button" className="nt-link-button" onClick={onRefresh} disabled={busy}><RefreshCw size={13} /> 只读刷新</button><button type="button" className="nt-link-button" onClick={onReset}><PlusIcon /> 新建项目</button></div>}
          {!snapshot && <p className="nt-action-note">锁定会保存服务端当前策略推荐，不会读取真实历史强度；比较只改变观察焦点，不改写推荐。</p>}
          {snapshot?.status === 'awaiting_user_confirmation' && <p className="nt-action-note amber">确认后只释放当前一条，并更新项目模型；不会自动重试。</p>}
        </div>
      </div>

      <div className="nt-bench-compare">
        <div className="nt-compare-head"><span>并排比较 / TWO CANDIDATES</span>{pending && <span className="nt-pending-flag"><LockKeyhole size={12} /> 预测已封存</span>}</div>
        <div className="nt-compare-grid">
          <CandidateCard row={selected} pending={pending?.row_id === selected?.row_id ? pending : null} active side="A" onSelect={onSelect} onCompare={onCompare} compare={compareIds.includes(selected?.row_id)} research={research} />
          <CandidateCard row={compareRow} active={false} pending={pending?.row_id === compareRow?.row_id ? pending : null} side="B" onSelect={onSelect} onCompare={onCompare} compare={compareIds.includes(compareRow?.row_id)} research={research} />
        </div>
        {selected && compareRow && <div className="nt-compare-summary"><Columns2 size={14} /><span>预测差 <strong>{number(Math.abs((pending?.row_id === selected.row_id ? pending.prediction : selected.prediction) - (pending?.row_id === compareRow.row_id ? pending.prediction : compareRow.prediction)), 2)} {meta.target.unit || ''}</strong></span><span>控制量不同：{controlEntries(selected.controls).filter(([key, value]) => Math.abs(Number(value) - Number(compareRow.controls[key])) > 1e-9).length} 项</span></div>}
        {pending && <div className="nt-pending-banner"><LockKeyhole size={15} /><div><strong>这条预测已经保存，但历史实测仍隐藏。</strong><p>{pending.reason || '服务端说明了推荐理由。'} 确认后才释放一条历史结果。</p></div><span>{number(pending.prediction, 2)} {meta.target.unit || ''}</span></div>}
        {last && <HistoryOutcome item={last} />}
        {snapshot?.status === 'budget_exhausted' && <div className="nt-done"><Check size={16} /><span>预算已用完。历史回放结束；没有新的现场实验。</span><button type="button" className="nt-link-button" onClick={onReset}><PlusIcon /> 新建项目</button></div>}
        {snapshot && ['release_uncertain', 'update_uncertain', 'update_failed'].includes(snapshot.status) && <div className="nt-stop"><ShieldAlert size={16} /><span>状态需要人工核查。系统不会自动重试或补写记录；请保存项目编号并只读刷新。</span></div>}
      </div>
    </div>
    <EvidencePrism pending={pending} last={last} hypothesis={last ? reflectionHypothesis : hypothesis} transition={transition} mode={mode} />
    {!research && last && <ReflectionCard last={last} hypothesis={reflectionHypothesis} transition={transition} onNavigate={onNavigate} onResearch={onResearch} />}
    <div className="nt-bench-foot"><span><History size={13} /> 项目 {snapshot?.project_id || '尚未创建'} · 剩余预算 {snapshot?.remaining_budget ?? budget} / {snapshot?.budget ?? budget}</span>{preview?.model_sha && <code>model {preview.model_sha.slice(0, 12)}…</code>}</div>
  </section>
}

function PlusIcon() { return <span className="nt-plus" aria-hidden="true">+</span> }
