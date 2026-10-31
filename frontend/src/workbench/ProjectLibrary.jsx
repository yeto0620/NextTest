import React, { useEffect, useMemo, useState } from 'react'
import { Archive, ChevronRight, CircleAlert, FileCheck2, GitCompareArrows, LoaderCircle, ShieldCheck, X } from 'lucide-react'

const strategyNames = { greedy_prediction: '最高预测', max_disagreement: '最大分歧', random: '随机' }
const compareCopy = {
  comparable_same_source_and_split: { title: '可描述比较', text: '来源与切分一致。仍只显示描述性事实，不生成排名。', tone: 'is-ready' },
  same_dataset_but_different_split: { title: '不可直接比较', text: '数据集相同，但数据切分不同。', tone: 'is-caution' },
  different_dataset: { title: '不可直接比较', text: '两份项目来自不同数据集。', tone: 'is-caution' },
  audit_failed: { title: '核验未通过', text: '至少一侧未通过只读审计；不展示部分比较。', tone: 'is-error' },
}

async function api(path, method = 'GET', body) {
  const response = await fetch(path, { method, headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || `请求失败（${response.status}）`)
  return data
}
function short(value) { return typeof value === 'string' && value ? value : '—' }
function metric(value) { return typeof value === 'number' ? String(value) : '—' }
function status(value) { return value === 'ready' ? '可继续' : value === 'pending' ? '待揭示' : value || '—' }

function ProjectCard({ item, selected, onClick }) {
  return <button type="button" className={`nt-library-card ${selected ? 'is-selected' : ''}`} onClick={onClick}>
    <span className="nt-library-card-head"><Archive size={15} /><code>{item.project_id}</code><ChevronRight size={15} /></span>
    <strong>{item.dataset_display_name || item.dataset_short_id || '已核验项目'}</strong>
    <span className="nt-library-card-meta"><em>{strategyNames[item.strategy] || item.strategy || '—'}</em><em>{status(item.status)}</em><em>{metric(item.revealed_count)}/{metric(item.budget)} 已揭示</em></span>
    <span className="nt-library-card-fingerprint"><i />{short(item.source_sha256_short)} <b>·</b> {short(item.split_sha256_short)}</span>
  </button>
}

function CardDetail({ card, loading, error, onCompare }) {
  if (loading) return <div className="nt-library-detail nt-library-empty"><LoaderCircle className="nt-spin" size={20} /><strong>正在核验公开证据</strong><span>只读取 P5-B 已封存的公开字段。</span></div>
  if (error) return <div className="nt-library-detail nt-library-empty is-error"><CircleAlert size={21} /><strong>档案不可用</strong><span>{error}</span></div>
  if (!card) return <div className="nt-library-detail nt-library-empty"><FileCheck2 size={22} /><strong>选择一份档案</strong><span>查看已核验的公开摘要与边界。</span></div>
  const summary = card.summary || {}; const brief = card.defense_brief || {}; const snapshot = card.snapshot_public || {}
  return <article className="nt-library-detail">
    <header><div><span className="nt-kicker">PUBLIC EVIDENCE CARD</span><h3>{card.dataset_public_metadata?.display_name || summary.dataset_display_name || '项目档案'}</h3><code>{card.project_id}</code></div><button type="button" className="nt-secondary-button" onClick={() => onCompare(card.project_id)}><GitCompareArrows size={14} />加入比较</button></header>
    <div className="nt-library-detail-grid"><div><span>策略</span><strong>{strategyNames[summary.strategy] || summary.strategy || '—'}</strong></div><div><span>已揭示</span><strong>{metric(brief.revealed_count ?? summary.revealed_count)} / {metric(summary.budget)}</strong></div><div><span>MAE</span><strong>{metric(brief.mae)}</strong></div><div><span>最大误差</span><strong>{metric(brief.max_absolute_error)}</strong></div></div>
    <section className="nt-library-fingerprint-block"><span>SOURCE / SPLIT</span><code>{short(snapshot.source_canonical_sha256)}</code><code>{short(snapshot.split_sha256)}</code></section>
    <p className="nt-library-detail-boundary">{Array.isArray(card.limitations) ? card.limitations[0] : '仅显示公开、已核验事实。'}</p>
  </article>
}

function CompareSurface({ result, loading, error, selection, onRemove }) {
  if (selection.length < 2) return <section className="nt-library-compare nt-library-compare-empty"><GitCompareArrows size={19} /><div><strong>选择两份档案</strong><span>比较只检查数据来源与切分是否一致，不生成胜负。</span></div></section>
  if (loading) return <section className="nt-library-compare nt-library-compare-empty"><LoaderCircle className="nt-spin" size={19} /><div><strong>正在检查可比性</strong><span>核验两侧已封存的公开摘要。</span></div></section>
  if (error) return <section className="nt-library-compare nt-library-compare-empty is-error"><CircleAlert size={19} /><div><strong>比较不可用</strong><span>{error}</span></div></section>
  if (!result) return null
  const kind = compareCopy[result.comparability] || compareCopy.audit_failed
  const fields = [['策略', 'strategy'], ['已揭示', 'revealed_count'], ['MAE', 'mae'], ['最大误差', 'max_error'], ['来源指纹', 'source_sha256_short'], ['切分指纹', 'split_sha256_short']]
  return <section className="nt-library-compare"><header><div><span className="nt-kicker">COMPARABILITY CHECK</span><h3>{kind.title}</h3><p>{kind.text}</p></div><span className={`nt-library-compare-seal ${kind.tone}`}><ShieldCheck size={15} />{result.comparability}</span></header><div className="nt-library-compare-ids">{selection.map(id => <button type="button" key={id} onClick={() => onRemove(id)}><code>{id}</code><X size={13} /></button>)}</div><div className="nt-library-compare-table" role="table" aria-label="项目公开证据比较"><div role="row" className="nt-library-compare-head"><span>字段</span><code>{result.left?.project_id}</code><code>{result.right?.project_id}</code></div>{fields.map(([label, key]) => <div role="row" key={key}><span>{label}</span><strong>{metric(result.left?.[key])}</strong><strong>{metric(result.right?.[key])}</strong></div>)}</div><footer>{result.shared_facts?.disclaimer || '描述性比较，不构成策略优越结论。'}</footer></section>
}

export default function ProjectLibrary({ active, onClose }) {
  const [library, setLibrary] = useState(null); const [selectedId, setSelectedId] = useState(''); const [card, setCard] = useState(null); const [selection, setSelection] = useState([]); const [comparison, setComparison] = useState(null); const [loading, setLoading] = useState(false); const [cardLoading, setCardLoading] = useState(false); const [compareLoading, setCompareLoading] = useState(false); const [error, setError] = useState(''); const [cardError, setCardError] = useState(''); const [compareError, setCompareError] = useState('')
  useEffect(() => { if (!active) return undefined; let cancelled = false; setLoading(true); setError(''); api('/api/library').then(data => { if (cancelled) return; setLibrary(data); const first = data.items?.[0]?.project_id; if (first) setSelectedId(current => current || first) }).catch(err => { if (!cancelled) setError(err.message) }).finally(() => { if (!cancelled) setLoading(false) }); return () => { cancelled = true } }, [active])
  useEffect(() => { if (!active) return undefined; const close = event => { if (event.key === 'Escape') onClose() }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close) }, [active, onClose])
  useEffect(() => { if (!active || !selectedId) return undefined; let cancelled = false; setCardLoading(true); setCardError(''); setCard(null); api(`/api/library/${encodeURIComponent(selectedId)}/card`).then(data => { if (!cancelled) setCard(data) }).catch(err => { if (!cancelled) setCardError(err.message) }).finally(() => { if (!cancelled) setCardLoading(false) }); return () => { cancelled = true } }, [active, selectedId])
  useEffect(() => { if (selection.length !== 2) { setComparison(null); return undefined } let cancelled = false; setCompareLoading(true); setCompareError(''); setComparison(null); api('/api/library/compare', 'POST', { left_project_id: selection[0], right_project_id: selection[1] }).then(data => { if (!cancelled) setComparison(data) }).catch(err => { if (!cancelled) setCompareError(err.message) }).finally(() => { if (!cancelled) setCompareLoading(false) }); return () => { cancelled = true } }, [selection])
  const items = useMemo(() => library?.items || [], [library])
  function addCompare(id) { setSelection(current => current.includes(id) ? current : current.length === 2 ? [current[1], id] : [...current, id]) }
  function removeCompare(id) { setSelection(current => current.filter(item => item !== id)) }
  if (!active) return null
  return <section className="nt-library" aria-label="项目档案库"><header className="nt-library-head"><div><span className="nt-kicker">READ-ONLY PROJECT LIBRARY</span><h2>实验档案</h2><p>已核验项目的公开证据摘要。比较先检查来源与切分，不做排名。</p></div><button type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭项目档案"><X size={18} /></button></header><div className="nt-library-river" aria-hidden="true"><i /><i /><i /><b /></div><div className="nt-library-layout"><aside className="nt-library-index"><header><span>PROJECTS</span><strong>{loading ? '…' : library?.count ?? 0}</strong></header>{error ? <div className="nt-library-index-error"><CircleAlert size={16} />{error}</div> : items.length ? <div className="nt-library-cards">{items.map(item => <ProjectCard key={item.project_id} item={item} selected={item.project_id === selectedId} onClick={() => setSelectedId(item.project_id)} />)}</div> : <div className="nt-library-index-empty">当前没有可公开展示的已核验项目。</div>}</aside><div className="nt-library-main"><CardDetail card={card} loading={cardLoading} error={cardError} onCompare={addCompare} /><CompareSurface result={comparison} loading={compareLoading} error={compareError} selection={selection} onRemove={removeCompare} /></div></div></section>
}
