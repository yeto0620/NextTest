import React from 'react'
import { Archive, Beaker, CircleHelp, Database, Download, GitCompareArrows, Keyboard, MessageCircleMore, MonitorPlay, Moon, Orbit, Radar, ScanSearch, Sparkles, Sun } from 'lucide-react'

const RESEARCH_ITEMS = [
  { id: 'mission', label: '观测', icon: ScanSearch },
  { id: 'atlas', label: '候选', icon: Orbit },
  { id: 'bench', label: '实验', icon: Beaker },
  { id: 'strategy', label: '策略', icon: GitCompareArrows },
  { id: 'trail', label: '证据', icon: Radar },
  { id: 'library', label: '档案', icon: Archive },
  { id: 'data', label: '数据', icon: Database },
]

const EXPLORE_ITEMS = [
  { id: 'mission', label: '导览', icon: ScanSearch },
  { id: 'atlas', label: '航图', icon: Orbit },
  { id: 'bench', label: '体验', icon: Beaker },
  { id: 'trail', label: '故事', icon: Radar },
]

export default function TopNavigation({ active, onNavigate, mode, onMode, status, datasetName, onStrategy, onData, onLibrary, onGuide, onExport, onShortcuts, onStage, onAssistant, theme, onTheme, onTour }) {
  const items = mode === 'research' ? RESEARCH_ITEMS : EXPLORE_ITEMS
  function select(item) {
    if (item.id === 'strategy') return onStrategy()
    if (item.id === 'library') return onLibrary()
    if (item.id === 'data') return onData()
    onNavigate(item.id)
  }
  return <header className="nt-topnav">
    <div className="nt-topnav-brand" aria-label="NextTest 实验决策工作台">
      <img className="nt-topnav-mark" src="/nexttest-mark.svg" alt="" width="30" height="30" />
      <span>NextTest</span><small>EXPERIMENTAL STUDIO</small>
    </div>
    <nav className="nt-topnav-links" aria-label="主功能" data-tour="nav">
      {items.map(item => {
        const Icon = item.icon
        const selected = active === item.id
        return <button type="button" key={item.id} data-tour={item.id} className={selected ? 'is-active' : ''} onClick={() => select(item)}>
          <Icon size={14} /><span>{item.label}</span>
        </button>
      })}
    </nav>
    <div className="nt-topnav-tools">
      {mode === 'research' && <span className="nt-topnav-dataset" title={datasetName || '当前数据集'}><i />{datasetName || '数据集'}</span>}
      <button type="button" className="nt-topnav-icon" onClick={onTour} title="新手引导" aria-label="打开新手引导"><Sparkles size={15} /></button>
      <button type="button" className="nt-topnav-icon" onClick={onTheme} title={theme === 'light' ? '切换到深色主题' : '切换到亮色主题'} aria-label={theme === 'light' ? '切换到深色主题' : '切换到亮色主题'}>{theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}</button>
      <div className="nt-mode" role="group" aria-label="信息密度" data-tour="mode">
        <button type="button" className={mode === 'research' ? 'is-selected' : ''} onClick={() => onMode('research')}>研究</button>
        <button type="button" className={mode === 'explore' ? 'is-selected' : ''} onClick={() => onMode('explore')}>科普</button>
      </div>
      {mode === 'research' && <><button type="button" className="nt-topnav-icon nt-topnav-assistant" onClick={onAssistant} title="科研智能体" aria-label="打开科研智能体"><MessageCircleMore size={15} /></button>
      <button type="button" className="nt-topnav-icon" onClick={onShortcuts} title="快捷键（?）" aria-label="打开快捷键"><Keyboard size={15} /></button>
      <button type="button" className="nt-topnav-icon" disabled={!onExport} onClick={onExport} title={onExport ? '导出当前项目' : '创建项目后可导出'} aria-label="导出当前项目"><Download size={15} /></button></>}
      {mode === 'explore' && <><button type="button" className="nt-topnav-icon nt-topnav-stage" onClick={onStage} title="演示模式" aria-label="打开演示模式"><MonitorPlay size={15} /></button>
      <button type="button" className="nt-topnav-icon" onClick={onGuide} title="使用方法" aria-label="使用方法"><CircleHelp size={16} /></button></>}
      <span className={`nt-topnav-status ${status ? 'is-live' : ''}`} title={status || '尚未创建项目'}><i />{status || 'READY'}</span>
    </div>
  </header>
}
