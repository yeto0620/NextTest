import React from 'react'
import { Clipboard, Database, Hash, LockKeyhole } from 'lucide-react'
import { controlEntries, number, statusLabel, strategyLabel, text } from './data'
import { useDataset, labelFor, unitFor } from './dataset'

function CopyValue({ value, label }) {
  const display = value ? `${value.slice(0, 22)}…` : '—'
  return <span className="nt-copy-value"><code title={value || '不可用'}>{display}</code>{value && <button type="button" className="nt-copy-button" title={`复制${label}`} aria-label={`复制${label}`} onClick={() => navigator.clipboard?.writeText(value)}><Clipboard size={11} /></button>}</span>
}

function Row({ label, children, reason }) {
  return <div className="nt-ledger-row"><dt>{label}</dt><dd>{children ?? '—'}{reason && <small>{reason}</small>}</dd></div>
}

export default function ResearchLedger({ view, preview, landscape, selectedCandidate, mode }) {
  const meta = useDataset()
  if (mode !== 'research') return null
  const snapshot = view?.snapshot
  const pending = view?.pending
  const last = view?.history?.at(-1)
  const controls = selectedCandidate?.controls || pending?.controls || {}
  return <section className="nt-ledger" id="ledger" aria-labelledby="nt-ledger-title">
    <header className="nt-ledger-head"><div><span className="nt-kicker">RESEARCH LEDGER / 科研核验信息</span><h2 id="nt-ledger-title">每个数字，都能回到来源</h2><p>只读展示当前 API 已有字段；没有的字段显示 <code>—</code>，不补时间戳或训练细节。</p></div><Hash size={20} /></header>
    <div className="nt-ledger-columns">
      <dl>
        <Row label="数据集"><span>{meta.displayName}</span><small className="nt-ledger-inline">{meta.isCustom ? '本地冻结数据；名称与单位来自 schema，标签不进入浏览器。' : '内置公开数据；名称来自实验配置，标签不进入浏览器。'}</small></Row>
        <Row label="当前训练行数">{snapshot?.observed_count != null ? `${snapshot.observed_count} 行` : '—'}<small className="nt-ledger-inline">初始 {Math.max(0, Number(snapshot?.observed_count || 0) - Number(snapshot?.revealed_count || 0))} 行，reveal 后追加</small></Row>
        <Row label="独立留出行数">{snapshot?.test_count != null ? `${snapshot.test_count} 行` : '—'}<small className="nt-ledger-inline">只用于最终核验，不进入推荐</small></Row>
        <Row label="数据 SHA"><CopyValue value={snapshot?.source_canonical_sha256} label="数据 SHA" /></Row>
        <Row label="分割 SHA"><CopyValue value={snapshot?.split_sha256} label="分割 SHA" /></Row>
        <Row label="留出 SHA"><CopyValue value={snapshot?.test_sha256} label="留出 SHA" /></Row>
        <Row label="模型 SHA"><CopyValue value={snapshot?.current_model_sha || preview?.model_sha} label="模型 SHA" /></Row>
        <Row label="初始模型 SHA"><CopyValue value={snapshot?.initial_model_sha} label="初始模型 SHA" /></Row>
      </dl>
      <dl>
        <Row label="目标">{snapshot?.goal === 'maximize' ? `最大化 ${meta.target.displayName}` : snapshot?.goal === 'minimize' ? `最小化 ${meta.target.displayName}` : '—'}</Row>
        <Row label="阈值">{snapshot?.threshold == null ? '—（未设置）' : `${number(snapshot.threshold, 2)} ${meta.target.unit || ''}`}</Row>
        <Row label="预算">{snapshot ? `${snapshot.revealed_count} / ${snapshot.budget} 次；剩余 ${snapshot.remaining_budget}` : '—'}</Row>
        <Row label="策略">{snapshot?.strategy ? strategyLabel(snapshot.strategy) : preview?.strategy ? `${strategyLabel(preview.strategy)}（预览）` : '—'}</Row>
        <Row label="当前状态">{snapshot ? statusLabel(snapshot.status) : '尚未创建项目'}</Row>
        <Row label="当前方案"><code>{selectedCandidate?.row_id || pending?.row_id || '—'}</code></Row>
        <Row label="方案配方">{controlEntries(controls, true).length ? <span className="nt-ledger-recipe">{controlEntries(controls, true).map(([key, value]) => <span key={key}><b>{labelFor(meta, key)}</b> {number(value, 2)} <small>{unitFor(meta, key)}</small></span>)}</span> : '—'}</Row>
        <Row label="预测 / 差异">{Number.isFinite(Number(selectedCandidate?.prediction ?? pending?.prediction)) ? <span>{number(selectedCandidate?.prediction ?? pending?.prediction, 2)} {meta.target.unit || ''} / {number(selectedCandidate?.disagreement ?? pending?.disagreement, 2)} {meta.target.unit || ''}</span> : '—'}<small className="nt-ledger-inline">差异是树间标准差，不是概率</small></Row>
        <Row label="已公布实测">{last ? `${number(last.revealed_target, 2)} ${meta.target.unit || ''}（${last.row_id}）` : '—'}<small className="nt-ledger-inline">{last ? `绝对误差 ${number(last.absolute_error, 2)} ${meta.target.unit || ''}` : '尚未公布'}</small></Row>
        <Row label="时间戳 / 字段确认表单">—<small className="nt-ledger-inline">当前 API 未提供，不补造</small></Row>
        <Row label="完整训练参数">—<small className="nt-ledger-inline">当前 API 未提供</small></Row>
      </dl>
    </div>
    <footer><span><Database size={12} /> {snapshot ? '项目事实来自 snapshot / audit / history' : '尚未创建项目；显示可用数据边界'}</span><span><LockKeyhole size={12} /> target 仅在 reveal 后进入页面</span><span>{text(snapshot?.project_id)}</span></footer>
  </section>
}
