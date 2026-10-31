import React, { useEffect, useMemo, useState } from 'react'
import { Radar } from 'lucide-react'
import Landscape from './Landscape'
import TopNavigation from './workbench/TopNavigation'
import WorkspaceShortcuts from './workbench/WorkspaceShortcuts'
import PresentationStage from './workbench/PresentationStage'
import EvidenceAssistant from './workbench/EvidenceAssistant'
import EvidencePackageDrawer from './workbench/EvidencePackageDrawer'
import ProjectLibrary from './workbench/ProjectLibrary'
import MissionDeck from './workbench/MissionDeck'
import ResearchCockpit from './workbench/ResearchCockpit'
import GuideDrawer from './workbench/GuideDrawer'
import PossibilityAtlas from './workbench/PossibilityAtlas'
import SelectionDetail from './workbench/SelectionDetail'
import ExperimentBench from './workbench/ExperimentBench'
import EvidenceTrail from './workbench/EvidenceTrail'
import ResearchLedger from './workbench/ResearchLedger'
import DataDock from './workbench/DataDock'
import DatasetPassport from './workbench/DatasetPassport'
import StrategyObservatory from './workbench/StrategyObservatory'
import { CONCRETE_META, DatasetMetaProvider, metaFromView } from './workbench/dataset'
import { STRATEGY_META, comparePair, controlEntries, number, statusLabel, strategyLabel } from './workbench/data'

const PROJECT_KEY = 'nexttest_v3_project_id'
const CUSTOM_DATASET_KEY = 'nexttest.customDataset'
const STATUS_ORDER = ['mission', 'atlas', 'bench', 'trail']

async function request(path, method = 'GET', body) {
  const response = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    const message = typeof detail === 'string' ? detail : detail?.message || `请求失败（${response.status}）`
    const error = new Error(message)
    error.uncertain = data.uncertain || detail?.uncertain
    error.projectId = detail?.project_id
    throw error
  }
  return data
}

function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 900)
}

function report(view, meta) {
  const snapshot = view.snapshot
  const targetUnit = meta?.target?.unit || 'unit not supplied'
  return [
    '# NextTest 历史回放证据摘要', '',
    `这是 ${meta?.displayName || '当前数据集'} 的历史数据回放，不是新做的物理试验。`, '',
    `- 项目：${snapshot.project_id}`,
    `- 状态：${statusLabel(snapshot.status)}`,
    `- 目标：${snapshot.goal === 'maximize' ? '最大化' : '最小化'} ${meta?.target?.displayName || '目标'}`,
    `- 策略：${strategyLabel(snapshot.strategy)}`,
    `- 预算：${snapshot.budget}；已揭示：${snapshot.revealed_count}`,
    `- 数据 SHA：${snapshot.source_canonical_sha256}`,
    `- 切分 SHA：${snapshot.split_sha256}`,
    `- 初始模型 SHA：${snapshot.initial_model_sha}`,
    `- 当前模型 SHA：${snapshot.current_model_sha}`,
    `- 事件链 SHA：${view.audit?.event_chain_sha256 || '—'}`, '',
    `| 轮次 | 历史方案 | 揭示前预测 ${targetUnit} | 历史实测 ${targetUnit} | 绝对误差 ${targetUnit} |`,
    '|---:|---|---:|---:|---:|',
    ...(view.history || []).map(item => `| ${item.round} | ${item.row_id} | ${number(item.prediction, 3)} | ${number(item.revealed_target, 3)} | ${number(item.absolute_error, 3)} |`),
    '', '边界：固定历史数据上的探索性回放；不证明策略优越、成本节省、因果或工业部署。', '',
  ].join('\n')
}

export default function App() {
  const [landscape, setLandscape] = useState(null)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [view, setView] = useState(null)
  const [strategy, setStrategy] = useState('greedy_prediction')
  const [goal, setGoal] = useState('maximize')
  const [threshold, setThreshold] = useState(null)
  const [budget, setBudget] = useState(3)
  const [selection, setSelection] = useState(null)
  const [compareIds, setCompareIds] = useState([])
  const [mode, setMode] = useState('research')
  const [viewMode, setViewMode] = useState('table')
  const [active, setActive] = useState('mission')
  const [workspace, setWorkspace] = useState('mission')
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [presentationOpen, setPresentationOpen] = useState(false)
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [packageOpen, setPackageOpen] = useState(false)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [packageBusy, setPackageBusy] = useState(false)
  const [packageError, setPackageError] = useState('')
  const [evidencePackage, setEvidencePackage] = useState(null)
  const [guideOpen, setGuideOpen] = useState(false)
  const [resumeId, setResumeId] = useState(() => localStorage.getItem(PROJECT_KEY) || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [scanning, setScanning] = useState(false)
  const [dockOpen, setDockOpen] = useState(false)
  const [customDataset, setCustomDataset] = useState(() => { try { return JSON.parse(localStorage.getItem(CUSTOM_DATASET_KEY) || 'null') } catch { return null } })
  const [passportOpen, setPassportOpen] = useState(false)
  const [observatoryOpen, setObservatoryOpen] = useState(false)
  const [hypothesis, setHypothesis] = useState({ choice: null, note: '', skipped: false })
  const [hypothesisLocal, setHypothesisLocal] = useState(false)
  const [reflectionHypothesis, setReflectionHypothesis] = useState(null)

  const snapshot = view?.snapshot
  const projectId = snapshot?.project_id
  const datasetId = customDataset?.dataset_id || view?.dataset?.dataset_id || null
  const isCustom = Boolean(datasetId)
  const datasetMeta = useMemo(() => customDataset ? metaFromView({ dataset: customDataset }) : view?.dataset ? metaFromView(view) : CONCRETE_META, [customDataset, view?.dataset])
  const previewProjectId = projectId && snapshot?.status === 'ready' ? projectId : null

  const navigate = id => {
    setActive(id)
    setWorkspace(id)
    window.setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 0)
  }

  useEffect(() => {
    const stored = localStorage.getItem(PROJECT_KEY)
    if (stored && stored.startsWith('p3_')) request(`/api/custom/projects/${encodeURIComponent(stored)}`).then(data => { setView(data); setCustomDataset(data.dataset) }).catch(() => {
      setError('保存的自定义项目未通过只读核查；不会改写原记录。')
    })
    else if (stored) request(`/api/projects/${encodeURIComponent(stored)}`).then(data => { setView(data); setCustomDataset(null); localStorage.removeItem(CUSTOM_DATASET_KEY) }).catch(() => {
      setError('保存的项目未通过只读核查；不会改写原记录。')
    })
    else request('/api/landscape').then(setLandscape).catch(err => setError(`已观测数据暂不可用：${err.message}`))
  }, [])

  useEffect(() => {
    if (!datasetId) {
      let cancelled = false
      request('/api/landscape').then(data => { if (!cancelled) setLandscape(data) }).catch(err => { if (!cancelled) setError(`已观测数据暂不可用：${err.message}`) })
      return () => { cancelled = true }
    }
    let cancelled = false
    request(`/api/custom/datasets/${encodeURIComponent(datasetId)}/landscape`).then(data => { if (!cancelled) setLandscape(data) }).catch(err => { if (!cancelled) setError(`自定义数据图层不可用：${err.message}`) })
    return () => { cancelled = true }
  }, [datasetId])

  useEffect(() => {
    if (view && snapshot?.status !== 'ready') return undefined
    let cancelled = false
    setPreviewLoading(true)
    const path = isCustom ? '/api/custom/preview' : '/api/preview'
    const body = isCustom ? { dataset_id: datasetId, goal, strategy, threshold, project_id: previewProjectId } : { goal, strategy, threshold, project_id: previewProjectId }
    request(path, 'POST', body)
      .then(data => { if (!cancelled) { setPreview(data); setError('') } })
      .catch(err => { if (!cancelled && !String(err.message).includes('candidate preview not allowed')) setError(`候选投影不可用：${err.message}`) })
      .finally(() => { if (!cancelled) setPreviewLoading(false) })
    return () => { cancelled = true }
  }, [strategy, goal, threshold, previewProjectId, snapshot?.status, datasetId, isCustom])

  useEffect(() => {
    const sections = STATUS_ORDER.map(id => document.getElementById(id)).filter(Boolean)
    if (!sections.length) return undefined
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
      if (visible) setActive(visible.target.id)
    }, { rootMargin: '-20% 0px -55% 0px', threshold: [0.15, 0.4] })
    sections.forEach(section => observer.observe(section))
    return () => observer.disconnect()
  }, [landscape, view])

  useEffect(() => {
    const onKeyDown = event => {
      const target = event.target
      const typing = target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName)
      if (event.key === 'Escape') { setShortcutsOpen(false); return }
      if (typing || event.ctrlKey || event.metaKey || event.altKey) return
      const key = event.key.toLowerCase()
      const workspaces = { '1': 'mission', '2': 'atlas', '3': 'bench', '4': 'trail' }
      if (workspaces[key]) { event.preventDefault(); navigate(workspaces[key]); return }
      if (key === 's') { event.preventDefault(); setActive('strategy'); setObservatoryOpen(true); return }
      if (key === 'a') { event.preventDefault(); setAssistantOpen(true); return }
      if (key === 'l') { event.preventDefault(); setLibraryOpen(true); setActive('library'); return }
      if (event.key === '?') { event.preventDefault(); setShortcutsOpen(true) }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  const revealedIds = useMemo(() => new Set((view?.history || []).map(item => item.row_id)), [view?.history])
  const candidates = useMemo(() => {
    const rows = (preview?.rows || []).filter(row => !revealedIds.has(row.row_id))
    const pending = view?.pending
    if (pending && !rows.some(row => row.row_id === pending.row_id)) {
      rows.push({ row_id: pending.row_id, controls: pending.controls, prediction: pending.prediction, disagreement: pending.disagreement })
    }
    return rows
  }, [preview, view?.pending, revealedIds])

  useEffect(() => {
    const pending = view?.pending
    if (pending) {
      setSelection({ kind: 'candidate', rowId: pending.row_id })
      return
    }
    if (!candidates.length) return
    setSelection(current => {
      if (current?.kind === 'candidate' && candidates.some(row => row.row_id === current.rowId)) return current
      const preferred = candidates.some(row => row.row_id === preview?.selected?.row_id) ? preview.selected.row_id : candidates[0].row_id
      return { kind: 'candidate', rowId: preferred }
    })
  }, [view?.pending?.row_id, preview?.selected?.row_id, candidates.length, view?.snapshot?.status])

  useEffect(() => {
    if (!selection || selection.kind !== 'candidate') return
    const selectedId = selection.rowId
    const ranked = comparePair(candidates, selectedId, strategy, goal)
    const fallback = ranked.find(row => row.row_id !== selectedId)?.row_id
    setCompareIds(prev => {
      const valid = prev.filter(id => candidates.some(row => row.row_id === id) && id !== selectedId)
      if (valid.length >= 1) return [selectedId, ...valid.slice(0, 1)]
      return fallback ? [selectedId, fallback] : [selectedId]
    })
  }, [selection?.rowId, candidates, strategy, goal])

  useEffect(() => {
    if (view?.history?.length) {
      setScanning(true)
      const timer = window.setTimeout(() => setScanning(false), 950)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [view?.history?.length])

  const selectedCandidate = selection?.kind === 'candidate' ? candidates.find(row => row.row_id === selection.rowId) || null : null
  const benchSelectedId = selection?.kind === 'candidate' ? selection.rowId : preview?.selected?.row_id || null
  const selectedObserved = selection?.kind === 'observed' ? landscape?.rows?.find(row => row._row_id === selection.rowId) || null : null
  const compareCandidate = selection?.kind === 'candidate' ? candidates.find(row => compareIds.includes(row.row_id) && row.row_id !== selection.rowId) || null : null

  function chooseCandidate(rowId) { setSelection({ kind: 'candidate', rowId }) }
  function chooseObserved(point) { if (point?.id) setSelection({ kind: 'observed', rowId: point.id }) }
  function addCompare(rowId) {
    setSelection({ kind: 'candidate', rowId })
    setCompareIds(prev => prev.includes(rowId) ? prev : [selection?.rowId || rowId, rowId].filter(Boolean).slice(0, 2))
  }

  async function run(task) {
    setBusy(true); setError(''); setNotice('')
    try { await task() } catch (err) {
      if (err.projectId) { setResumeId(err.projectId); localStorage.setItem(PROJECT_KEY, err.projectId) }
      setError(err.message + (err.uncertain ? ' 请使用项目编号只读恢复，不要重试写入。' : ''))
    } finally { setBusy(false) }
  }

  async function lockNext() {
    await run(async () => {
      setHypothesisLocal(true)
      let current = view
      if (!current) {
        current = isCustom ? await request('/api/custom/projects', 'POST', { dataset_id: datasetId, goal, strategy, budget, threshold }) : await request('/api/projects', 'POST', { goal, strategy, budget, threshold })
        setView(current)
        localStorage.setItem(PROJECT_KEY, current.snapshot.project_id)
        if (isCustom && customDataset) localStorage.setItem(CUSTOM_DATASET_KEY, JSON.stringify(customDataset))
        setResumeId(current.snapshot.project_id)
      }
      const pending = isCustom ? await request(`/api/custom/projects/${current.snapshot.project_id}/recommend`, 'POST') : await request(`/api/projects/${current.snapshot.project_id}/recommend`, 'POST')
      setView(pending)
      setReflectionHypothesis(null)
      setSelection({ kind: 'candidate', rowId: pending.pending.row_id })
      setNotice('预测已封存。确认前，这条历史实测对浏览器仍然不可见。')
    })
  }

  async function reveal(recommendationId) {
    await run(async () => {
      const revealed = isCustom ? await request(`/api/custom/projects/${projectId}/reveal`, 'POST', { recommendation_id: recommendationId }) : await request(`/api/projects/${projectId}/reveal`, 'POST', { recommendation_id: recommendationId })
      setView(revealed)
      setReflectionHypothesis(hypothesis)
      setHypothesis({ choice: null, note: '', skipped: false })
      setHypothesisLocal(false)
      setNotice('已释放一条历史实测，并完成模型更新。')
    })
  }

  async function refresh() {
    if (!projectId) return
    await run(async () => { setView(await request(isCustom ? `/api/custom/projects/${encodeURIComponent(projectId)}` : `/api/projects/${encodeURIComponent(projectId)}`)) })
  }

  async function resume(id) {
    if (!id) return
    await run(async () => {
      const resumed = id.startsWith('p3_') ? await request(`/api/custom/projects/${encodeURIComponent(id)}`) : await request(`/api/projects/${encodeURIComponent(id)}`)
      setView(resumed)
      setCustomDataset(resumed.dataset || null)
      if (resumed.dataset) localStorage.setItem(CUSTOM_DATASET_KEY, JSON.stringify(resumed.dataset))
      else localStorage.removeItem(CUSTOM_DATASET_KEY)
      setResumeId(id)
      localStorage.setItem(PROJECT_KEY, id)
      setSelection(resumed.pending ? { kind: 'candidate', rowId: resumed.pending.row_id } : null)
      setHypothesis({ choice: null, note: '', skipped: false })
      setHypothesisLocal(false)
      setReflectionHypothesis(null)
      setNotice('项目已只读恢复；没有重做计算。本地预判不会随项目恢复。')
    })
  }

  function useDemo() { setCustomDataset(null); setView(null); setPreview(null); setLandscape(null); setSelection(null); setCompareIds([]); localStorage.removeItem(PROJECT_KEY); localStorage.removeItem(CUSTOM_DATASET_KEY); setDockOpen(false); setError(''); setNotice(''); setActive('mission') }

  function completeDock(dataset) { setCustomDataset(dataset); localStorage.setItem(CUSTOM_DATASET_KEY, JSON.stringify(dataset)); setView(null); setPreview(null); setSelection(null); setCompareIds([]); localStorage.removeItem(PROJECT_KEY); setDockOpen(false); setResumeId(''); setNotice('数据护照已冻结；现在为这份数据建立一次历史回放项目。'); setActive('mission') }

  function reset() {
    setView(null); setPreview(null); setSelection(null); setCompareIds([]); setError(''); setNotice(''); setResumeId('')
    setHypothesis({ choice: null, note: '', skipped: false }); setHypothesisLocal(false); setReflectionHypothesis(null)
    localStorage.removeItem(PROJECT_KEY)
    setActive('mission')
  }

  function resetHypothesis() { setHypothesis({ choice: null, note: '', skipped: false }); setHypothesisLocal(false) }
  function changeStrategy(id) { setStrategy(id); setSelection(null); setCompareIds([]); resetHypothesis() }
  function changeGoal(id) { setGoal(id); setSelection(null); setCompareIds([]); resetHypothesis() }
  function changeThreshold(value) { setThreshold(value); setSelection(null); setCompareIds([]); resetHypothesis() }
  function changeMode(nextMode) {
    const next = nextMode === 'explore' ? 'explore' : 'research'
    setMode(next)
    setWorkspace('mission')
    setActive('mission')
    setViewMode(next === 'research' ? 'table' : 'atlas')
    setLibraryOpen(false)
    setObservatoryOpen(false)
    setDockOpen(false)
    window.setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 0)
  }
  function openResearch() { setMode('research'); setWorkspace('trail'); setActive('trail'); window.setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 0) }

  async function openEvidencePackage() {
    if (!projectId) return
    setPackageOpen(true); setPackageBusy(true); setPackageError(''); setEvidencePackage(null)
    try {
      const path = projectId.startsWith('p3_') ? `/api/custom/projects/${encodeURIComponent(projectId)}/evidence-package` : `/api/projects/${encodeURIComponent(projectId)}/evidence-package`
      setEvidencePackage(await request(path))
    } catch (err) {
      setPackageError(err.message)
    } finally {
      setPackageBusy(false)
    }
  }

  const onDownload = snapshot ? openEvidencePackage : null

  return <DatasetMetaProvider meta={datasetMeta}><div className={`nt-app nt-density-${mode}`}>
    <main className="nt-main">
      <TopNavigation active={libraryOpen ? 'library' : observatoryOpen ? 'strategy' : dockOpen ? 'data' : active} onNavigate={navigate} mode={mode} onMode={changeMode} status={snapshot?.status}
        datasetName={datasetMeta.name} onStrategy={() => { setActive('strategy'); setObservatoryOpen(true) }} onData={() => { setActive('data'); setDockOpen(true) }}
        onLibrary={() => { setActive('library'); setLibraryOpen(true) }} onGuide={() => setGuideOpen(true)} onExport={onDownload} onShortcuts={() => setShortcutsOpen(true)} onStage={() => setPresentationOpen(true)} onAssistant={() => setAssistantOpen(true)} />

      <div className={`nt-content nt-workspace nt-workspace-${workspace}`}>
        {(error || notice) && <div role="alert" className={`nt-message ${error ? 'is-error' : ''}`}>{error || notice}</div>}
        {workspace === 'mission' && mode === 'research' && <ResearchCockpit landscape={landscape} preview={preview} view={view} strategy={strategy}
          selectedCandidate={selectedCandidate} compareCandidate={compareCandidate} selection={selection} onSelectObserved={chooseObserved}
          onNavigate={navigate} onStrategy={() => { setActive('strategy'); setObservatoryOpen(true) }}
          onLibrary={() => { setActive('library'); setLibraryOpen(true) }} onData={() => { setActive('data'); setDockOpen(true) }}
          onAssistant={() => setAssistantOpen(true)} resumeId={resumeId} setResumeId={setResumeId} onResume={resume} busy={busy} />}
        {workspace === 'mission' && mode === 'explore' && <MissionDeck landscape={landscape} preview={preview} view={view} strategy={strategy} selectedCandidate={selectedCandidate} compareCandidate={compareCandidate}
          selection={selection} onSelectObserved={chooseObserved} onNavigate={navigate} onGuide={() => setGuideOpen(true)}
          resumeId={resumeId} setResumeId={setResumeId} onResume={resume} busy={busy} mode={mode} />}

        {workspace === 'atlas' && <><div className="nt-atlas-layout">
          <PossibilityAtlas observedRows={landscape?.rows || []} candidates={candidates} selectedId={selection?.kind === 'candidate' ? selection.rowId : null}
            compareIds={compareIds} onSelect={chooseCandidate} onCompare={addCompare} viewMode={viewMode} onViewMode={setViewMode}
            view={view} mode={mode} hideAside loading={previewLoading} strategy={strategy} onStrategy={changeStrategy} preview={preview} />
          <SelectionDetail selection={selection} candidate={selectedCandidate} observed={selectedObserved} view={view} mode={mode}
            compareIds={compareIds} onCompare={addCompare} />
        </div>{previewLoading && <div className="nt-inline-loading"><span className="nt-scan-line" /> 正在读取候选投影…</div>}
        <details className="nt-3d-details">
          <summary><Radar size={15} /><span>三维已知材料空间</span><small>现有功能 / 只显示已观测记录</small><Chevron /></summary>
          <Landscape landscape={landscape} pending={view?.pending} selectedId={selection?.kind === 'observed' ? selection.rowId : null} onSelectObserved={chooseObserved} />
        </details></>}

        {workspace === 'bench' && <ExperimentBench preview={preview} view={view} candidates={candidates} selectedId={benchSelectedId}
          compareIds={compareIds} strategy={strategy} goal={goal} threshold={threshold} budget={budget} busy={busy} mode={mode}
          hypothesis={hypothesis} hypothesisLocal={hypothesisLocal} reflectionHypothesis={reflectionHypothesis} transition={view?.transition}
          onHypothesisChange={value => { setHypothesis(value); setHypothesisLocal(true) }} onHypothesisSkip={() => { setHypothesis({ choice: null, note: '', skipped: true }); setHypothesisLocal(true) }}
          onNavigate={navigate} onResearch={openResearch}
          onSelect={chooseCandidate} onCompare={addCompare} onStrategy={changeStrategy} onGoal={changeGoal} onThreshold={changeThreshold}
          onBudget={setBudget} onLock={lockNext} onReveal={reveal} onRecommend={lockNext} onRefresh={refresh} onReset={reset} />}

        {workspace === 'trail' && <><EvidenceTrail view={view} landscape={landscape} preview={preview} mode={mode} scanning={scanning} onDownload={onDownload} transition={view?.transition} />
        {mode === 'research' && <ResearchLedger view={view} preview={preview} landscape={landscape} selectedCandidate={selectedCandidate} mode={mode} />}</>}
        <footer className="nt-footer"><span>NextTest · 实验决策工作台</span><span>历史回放 / 非生产试验 / 关联不等于因果</span><span>{snapshot ? `${strategyLabel(snapshot.strategy)} · ${snapshot.revealed_count}/${snapshot.budget}` : '尚未创建项目'}</span></footer>
      </div>
    </main>
    <GuideDrawer open={guideOpen} onClose={() => setGuideOpen(false)} onNavigate={navigate} />
    <WorkspaceShortcuts open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} onNavigate={navigate}
      onStrategy={() => { setActive('strategy'); setObservatoryOpen(true) }} onGuide={() => setGuideOpen(true)} onAssistant={() => setAssistantOpen(true)} onLibrary={() => { setActive('library'); setLibraryOpen(true) }} />
    <PresentationStage open={presentationOpen} onClose={() => setPresentationOpen(false)} landscape={landscape} view={view} preview={preview}
      selectedCandidate={selectedCandidate} compareCandidate={compareCandidate} selection={selection} onSelectObserved={chooseObserved} onNavigate={navigate} />
    <EvidenceAssistant open={assistantOpen} onClose={() => setAssistantOpen(false)} view={view} selectedCandidate={selectedCandidate}
      onNavigate={id => { setAssistantOpen(false); navigate(id) }} onData={() => { setAssistantOpen(false); setActive('data'); setDockOpen(true) }} />
    <EvidencePackageDrawer open={packageOpen} onClose={() => setPackageOpen(false)} busy={packageBusy} error={packageError} packageData={evidencePackage}
      onMarkdown={() => evidencePackage && download(`NextTest_${evidencePackage.project_id}_evidence.md`, evidencePackage.markdown, 'text/markdown;charset=utf-8')}
      onJson={() => evidencePackage && download(`NextTest_${evidencePackage.project_id}_evidence.json`, `${JSON.stringify(evidencePackage, null, 2)}\n`, 'application/json;charset=utf-8')} />
    <ProjectLibrary active={libraryOpen} onClose={() => { setLibraryOpen(false); setActive(workspace) }} />
    {dockOpen && <DataDock onClose={() => { setDockOpen(false); setActive(workspace) }} onUseDemo={useDemo} onComplete={completeDock} mode={mode} />}
    <DatasetPassport open={passportOpen} dataset={customDataset || view?.dataset || null} onCompare={() => { setPassportOpen(false); setObservatoryOpen(true) }} onClose={() => setPassportOpen(false)} />
    <StrategyObservatory open={observatoryOpen} datasetId={customDataset?.dataset_id || view?.dataset?.dataset_id || 'demo-concrete'} onClose={() => { setObservatoryOpen(false); setActive(workspace) }} onPassport={() => { setObservatoryOpen(false); setPassportOpen(true) }} mode={mode} onMode={changeMode} />
  </div></DatasetMetaProvider>
}

function Chevron() { return <span className="nt-chevron" aria-hidden="true">＋</span> }
