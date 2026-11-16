import React, { useState } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { ArrowRight, Beaker, Check, ChevronRight, Columns2, History, LockKeyhole, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react'
import { STRATEGY_META, controlEntries, number, statusLabel, strategyLabel } from './data'
import { useDataset, labelFor } from './dataset'
import HypothesisSlip from './HypothesisSlip'
import EvidencePrism from './EvidencePrism'
import ReflectionCard from './ReflectionCard'

function CandidateCard({ row, active, pending, compare, onSelect, onCompare, side, research }) {
  const meta = useDataset()
  if (!row) return <div className="nt-compare-card nt-compare-empty"><ShieldAlert size={16} /><strong>没有第二个方案</strong><p>后端没有返回可比较的方案；界面不会编造对照。</p></div>
  const prediction = pending ? pending.prediction : row.prediction
  const disagreement = pending ? pending.disagreement : row.disagreement
  const controls = pending ? pending.controls : row.controls
  return <article className={`nt-compare-card ${active ? 'is-active' : ''} ${pending ? 'is-pending' : ''}`} onClick={() => onSelect(row.row_id)}>
    <header><span className="nt-kicker">{side === 'A' ? '方案 A' : '方案 B'} / {row.row_id}</span><span className={`nt-state ${pending ? 'nt-state-pending' : 'nt-state-open'}`}>{pending ? '已锁定 · 未查看' : '方案 · 未查看'}</span></header>
    <div className="nt-compare-number"><span>预测 {meta.target.displayName}</span><strong>{number(prediction, 2)} <em>{meta.target.unit || 'unit not supplied'}</em></strong></div>
    <div className="nt-compare-facts"><div><span>模型分歧</span><strong>{disagreement == null ? '—' : `${number(disagreement, 2)} ${meta.target.unit || ''}`}</strong></div><div><span>历史结果</span><strong className="nt-missing">— 未查看</strong></div></div>
    <details className="nt-candidate-parameters" onClick={event => event.stopPropagation()}><summary>查看配方参数</summary><dl>{controlEntries(controls).map(([key, value]) => <div key={key}><dt>{labelFor(meta, key)}</dt><dd>{number(value, 1)}</dd></div>)}</dl></details>
    <footer><button type="button" className="nt-link-button" onClick={event => { event.stopPropagation(); onCompare(row.row_id) }}><Columns2 size={12} /> {compare ? '正在对比' : '与它对比'}</button><span>{pending ? '确认后查看结果' : '系统预览'}</span></footer>
  </article>
}

function HistoryOutcome({ item }) {
  const meta = useDataset()
  if (!item) return null
  return <div className="nt-outcome"><div><span>封存预测</span><strong>{number(item.prediction, 2)} <em>{meta.target.unit || ''}</em></strong></div><ArrowRight size={16} /><div><span>历史结果</span><strong>{number(item.revealed_target, 2)} <em>{meta.target.unit || ''}</em></strong></div><small>绝对误差 {number(item.absolute_error, 2)} {meta.target.unit || ''} · 这一条结果不证明某种方法整体更好</small></div>
}

export default function ExperimentBench(props) {
  const [helpTopic, setHelpTopic] = useState(null)
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
  const roundComplete = Boolean(last && snapshot?.status === 'ready')
  const help = {
    strategy: '这是挑选下一条历史方案的方法：按预测值、按模型分歧，或随机选作参照。选法不同，推荐顺序可能不同；这里不证明哪一种整体更好。',
    goal: '选择优先查看预测强度较高或较低的方案。参考线只是你设定的目标，不是模型保证，也不改变历史实测。',
    budget: '查看次数是你最多愿意揭示多少条旧实验记录。每次只揭示一条，不会在现实中制作或测试材料。',
  }
  const helpButton = topic => <button type="button" className="nt-help" title={`解释${topic === 'strategy' ? '策略' : topic === 'goal' ? '目标' : '查看次数'}`} aria-label={`解释${topic === 'strategy' ? '策略' : topic === 'goal' ? '目标' : '查看次数'}`} aria-expanded={helpTopic === topic} aria-controls={`nt-help-${topic}`} onClick={() => setHelpTopic(current => current === topic ? null : topic)}>?</button>
  const helpText = topic => helpTopic === topic && <p id={`nt-help-${topic}`} className="nt-control-help" role="status">{help[topic]}</p>
  const actionLabel = pending ? '揭晓历史结果' : roundComplete ? '继续下一轮' : '锁定预测'
  return <section className="nt-bench" id="bench" aria-labelledby="nt-bench-title">
    <header className="nt-section-head">
      <div><span className="nt-kicker">第 {snapshot?.revealed_count ? snapshot.revealed_count + 1 : 1} 轮</span><h2 id="nt-bench-title">{pending ? '看结果' : roundComplete ? '本轮完成' : '锁定预测'}</h2></div>
      <div className="nt-bench-status"><span className={`nt-signal ${snapshot?.status && !['ready', 'awaiting_user_confirmation'].includes(snapshot.status) ? 'is-danger' : ''}`} />{snapshot ? statusLabel(snapshot.status) : '尚未锁定项目'}</div>
    </header>

    <div className="nt-bench-focus">
      <div><span className="nt-bench-focus-step">{pending ? '第 2 步 / 2' : '第 1 步 / 2'}</span>
        <strong>{pending ? '查看真实记录' : '先保存模型的预测'}</strong>
        <small>{pending ? '揭晓前，实测值不会出现在页面或请求中。' : selected ? `当前预览：${selected.row_id} · 预测 ${number(selected.prediction, 2)} ${meta.target.unit || ''}` : '正在读取方案，读完后即可继续。'}</small>
      </div>
      <div className="nt-bench-focus-action">
        {!snapshot && <Button label={busy ? '正在锁定…' : actionLabel} variant="primary" size="lg" className="nt-primary" isDisabled={!canLock} onClick={onLock}><LockKeyhole size={17} /> {busy ? '正在锁定…' : actionLabel}<ArrowRight size={17} /></Button>}
        {snapshot?.status === 'ready' && <Button label={busy ? '正在保存…' : actionLabel} variant="primary" size="lg" className="nt-primary" isDisabled={busy} onClick={onRecommend}><LockKeyhole size={17} /> {busy ? '正在保存…' : actionLabel}<ArrowRight size={17} /></Button>}
        {pending && <Button label={busy ? '正在读取…' : actionLabel} variant="primary" size="lg" className="nt-primary nt-primary-amber" isDisabled={busy} onClick={() => onReveal(pending.recommendation_id)}><Beaker size={17} /> {busy ? '正在读取…' : actionLabel}<ArrowRight size={17} /></Button>}
        {snapshot && <div className="nt-secondary-actions"><button type="button" className="nt-link-button" onClick={onRefresh} disabled={busy}><RefreshCw size={13} /> 刷新</button><button type="button" className="nt-link-button" onClick={onReset}><PlusIcon /> 新建项目</button></div>}
      </div>
    </div>

    {research && <details className="nt-research-details"><summary>研究详情 <small>项目编号、模型版本与内部状态</small></summary><div className="nt-research-operation-strip" aria-label="研究运行参数">
      <div><span>项目</span><code>{snapshot?.project_id || 'unfrozen'}</code></div>
      <div><span>策略</span><code>{strategyLabel(lockedStrategy)}</code></div>
      <div><span>阈值</span><code>{threshold ?? '—'}</code></div>
      <div><span>模型</span><code>{(snapshot?.current_model_sha || preview?.model_sha || '—').slice(0, 12)}</code></div>
      <div><span>状态</span><code>{snapshot?.status || 'preview'}</code></div>
    </div></details>}

    {!research && (!snapshot || ['ready', 'awaiting_user_confirmation'].includes(snapshot.status)) && <HypothesisSlip hypothesis={hypothesis} onChange={onHypothesisChange} onSkip={onHypothesisSkip} locked={Boolean(snapshot)} nextRound={Boolean(last)} savedWithoutLocal={Boolean(snapshot?.status === 'awaiting_user_confirmation' && !hypothesisLocal)} />}
    <div className="nt-bench-grid">
      <div className="nt-bench-controls">
        <div className="nt-control-block">
          <div className="nt-control-title"><span>01</span><strong>选择方法</strong>{!research && <small>{snapshot ? '项目策略已锁定' : '锁定前可切换'}</small>}{helpButton('strategy')}</div>
          {helpText('strategy')}
          <div className="nt-strategy-stack" role="group" aria-label="推荐策略">
            {Object.entries(STRATEGY_META).map(([id, meta]) => <button type="button" key={id} disabled={Boolean(snapshot)} className={strategy === id ? 'is-selected' : ''} onClick={() => onStrategy(id)}>
              <span><strong>{meta.label}</strong>{!research && <small>{meta.copy}</small>}</span><i className="nt-radio" />
            </button>)}
          </div>
          {snapshot && !research && <p className="nt-control-note">已锁定：{strategyLabel(snapshot.strategy)}。要换策略请新建项目；系统不会偷偷改已有记录。</p>}
        </div>

        <details className="nt-bench-options"><summary>更多设置 <small>目标 · 查看次数</small></summary>
        <div className="nt-control-block">
          <div className="nt-control-title"><span>02</span><strong>目标</strong><small>希望优先寻找哪一类方案</small>{helpButton('goal')}</div>
          {helpText('goal')}
          <div className="nt-segmented full"><button type="button" className={goal === 'maximize' ? 'is-selected' : ''} disabled={Boolean(snapshot)} onClick={() => onGoal('maximize')}>寻找较高强度</button><button type="button" className={goal === 'minimize' ? 'is-selected' : ''} disabled={Boolean(snapshot)} onClick={() => onGoal('minimize')}>寻找较低强度</button></div>
          <label className="nt-threshold"><input type="checkbox" checked={threshold != null} disabled={Boolean(snapshot)} onChange={e => onThreshold(e.target.checked ? 40 : null)} /> 添加目标参考线（可选）</label>
          {threshold != null && <div className="nt-threshold-input"><input type="number" min="-1000000" max="1000000" step="0.1" value={threshold} disabled={Boolean(snapshot)} onChange={e => onThreshold(Number(e.target.value))} aria-label="参考阈值" /><span>{meta.target.unit || ''}</span></div>}
        </div>

        <div className="nt-control-block">
          <div className="nt-control-title"><span>03</span><strong>查看次数</strong><small>{snapshot ? '项目创建后保持不变' : '最多打开几条历史结果'}</small>{helpButton('budget')}</div>
          {helpText('budget')}
          <div className="nt-budget-row"><input type="range" min="1" max="20" value={snapshot?.budget || budget} disabled={Boolean(snapshot)} onChange={e => onBudget(Number(e.target.value))} aria-label="查看次数" /><strong>{snapshot?.budget || budget} <small>次</small></strong></div>
          <div className="nt-range-ends"><span>1 次</span><span>20 次</span></div>
          <p className="nt-budget-explain">这不是实际实验次数；每次只打开一条过去已经完成的记录。</p>
        </div>
        </details>
      </div>

      <div className="nt-bench-compare">
        {!roundComplete && <>
        <div className="nt-compare-head"><span>两条方案 · 点击可切换</span>{pending && <span className="nt-pending-flag"><LockKeyhole size={12} /> 预测已保存</span>}</div>
        <div className="nt-compare-grid">
          <CandidateCard row={selected} pending={pending?.row_id === selected?.row_id ? pending : null} active side="A" onSelect={onSelect} onCompare={onCompare} compare={compareIds.includes(selected?.row_id)} research={research} />
          <CandidateCard row={compareRow} active={false} pending={pending?.row_id === compareRow?.row_id ? pending : null} side="B" onSelect={onSelect} onCompare={onCompare} compare={compareIds.includes(compareRow?.row_id)} research={research} />
        </div>
        {selected && compareRow && <div className="nt-compare-summary"><Columns2 size={14} /><span>预测差值 <strong>{number(Math.abs((pending?.row_id === selected.row_id ? pending.prediction : selected.prediction) - (pending?.row_id === compareRow.row_id ? pending.prediction : compareRow.prediction)), 2)} {meta.target.unit || ''}</strong></span><span>配方参数不同：{controlEntries(selected.controls).filter(([key, value]) => Math.abs(Number(value) - Number(compareRow.controls[key])) > 1e-9).length} 项</span></div>}
        {pending && <div className="nt-pending-banner"><LockKeyhole size={15} /><div><strong>预测已保存 · 实测仍隐藏</strong><p>点击“揭晓历史结果”查看实测。</p></div><span>{number(pending.prediction, 2)} {meta.target.unit || ''}</span></div>}
        </>}
        {last && <HistoryOutcome item={last} />}
        {roundComplete && <div className="nt-round-complete"><Check size={17} /><div><strong>本轮完成</strong><p>已对照预测与实测。</p></div><div><button type="button" className="nt-link-button" onClick={() => onNavigate('trail')}>查看本轮总结 <ChevronRight size={13} /></button><button type="button" className="nt-secondary-button" disabled={busy} onClick={onRecommend}>继续下一轮 <ArrowRight size={13} /></button></div></div>}
        {snapshot?.status === 'budget_exhausted' && <div className="nt-done"><Check size={16} /><span>预算已用完。历史回放结束；没有新的现场实验。</span><button type="button" className="nt-link-button" onClick={onReset}><PlusIcon /> 新建项目</button></div>}
        {snapshot && ['release_uncertain', 'update_uncertain', 'update_failed'].includes(snapshot.status) && <div className="nt-stop"><ShieldAlert size={16} /><span><strong>本轮已停止，记录仍保留。</strong> 系统不会自动重试或补写；先执行只读刷新，仍异常时保存项目编号。</span><button type="button" className="nt-link-button" onClick={onRefresh} disabled={busy}><RefreshCw size={13} /> 只读刷新</button></div>}
      </div>
    </div>
    <EvidencePrism pending={pending} last={last} hypothesis={last ? reflectionHypothesis : hypothesis} transition={transition} mode={mode} />
    {!research && last && <ReflectionCard last={last} hypothesis={reflectionHypothesis} transition={transition} onNavigate={onNavigate} onResearch={onResearch} />}
    <div className="nt-bench-foot"><span><History size={13} /> 项目 {snapshot?.project_id || '尚未创建'} · 剩余预算 {snapshot?.remaining_budget ?? budget} / {snapshot?.budget ?? budget}</span>{preview?.model_sha && <code>model {preview.model_sha.slice(0, 12)}…</code>}</div>
  </section>
}

function PlusIcon() { return <span className="nt-plus" aria-hidden="true">+</span> }
