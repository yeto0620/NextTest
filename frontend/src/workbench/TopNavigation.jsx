import React, { useState } from 'react'
import { Archive, Beaker, ChevronRight, CircleHelp, Database, Download, GitCompareArrows, Keyboard, MonitorPlay, Moon, Orbit, PanelLeftClose, Radar, ScanSearch, Sparkles, Sun } from 'lucide-react'

const PAGES = [
  { id: 'mission', label: '数据', icon: ScanSearch },
  { id: 'atlas', label: '方案', icon: Orbit },
  { id: 'bench', label: '实验', icon: Beaker },
  { id: 'trail', label: '结果', icon: Radar },
]

export default function TopNavigation({ active, onNavigate, mode, onMode, status, datasetName, onStrategy, onData, onLibrary, onGuide, onExport, onShortcuts, onStage, onAssistant, theme, onTheme, onTour, llmReady }) {
  const [compact, setCompact] = useState(false)
  return <aside className={`nt-topnav nt-sidebar ${compact ? 'is-compact' : ''}`} aria-label="工作区导航">
    <div className="nt-sidebar-head">
      <button type="button" className="nt-sidebar-brand" onClick={() => onNavigate('mission')} aria-label="NextTest 首页" title="NextTest 首页">
        <img src="/nexttest-mark.svg" alt="" width="32" height="32" />
        <span>NextTest</span>
      </button>
      <button type="button" className="nt-sidebar-collapse" onClick={() => setCompact(value => !value)} aria-label={compact ? '展开导航' : '收起导航'} title={compact ? '展开导航' : '收起导航'}>{compact ? <ChevronRight size={17} /> : <PanelLeftClose size={17} />}</button>
    </div>
    <nav className="nt-topnav-links nt-sidebar-nav" aria-label="主功能" data-tour="nav">
      <span className="nt-sidebar-label">工作区</span>
      {PAGES.map(({ id, label, icon: Icon }) => <button type="button" key={id} data-tour={id} className={active === id ? 'is-active' : ''} aria-current={active === id ? 'page' : undefined} title={label} onClick={() => onNavigate(id)}>
        <Icon size={19} strokeWidth={1.8} /><span>{label}</span>
      </button>)}
      <span className="nt-sidebar-label nt-sidebar-label-secondary">工具</span>
      <button type="button" className={active === 'library' ? 'is-active' : ''} title="档案" onClick={onLibrary}><Archive size={18} strokeWidth={1.8} /><span>档案</span></button>
      <button type="button" className={active === 'strategy' ? 'is-active' : ''} title="比较" onClick={onStrategy}><GitCompareArrows size={18} strokeWidth={1.8} /><span>比较</span></button>
      <button type="button" className={active === 'data' ? 'is-active' : ''} title="数据" onClick={onData}><Database size={18} strokeWidth={1.8} /><span>数据</span></button>
      <button type="button" title="导出" disabled={!onExport} onClick={onExport}><Download size={18} strokeWidth={1.8} /><span>导出</span></button>
    </nav>
    <div className="nt-sidebar-bottom">
      <button type="button" className="nt-sidebar-assistant" onClick={onAssistant} title="打开 AI 助手"><Sparkles size={18} /><span>AI 助手<small>{llmReady === false ? '本地帮助可用' : '解释公开证据'}</small></span><ChevronRight size={15} /></button>
      <div className="nt-sidebar-context"><strong>{datasetName || '演示数据'}</strong><small><i /> {status || '待开始'}</small></div>
      <div className="nt-mode nt-sidebar-mode" role="group" aria-label="信息密度" data-tour="mode">
        <button type="button" className={mode === 'research' ? 'is-selected' : ''} aria-pressed={mode === 'research'} title="研究：精简操作、完整字段" onClick={() => onMode('research')}>研究</button>
        <button type="button" className={mode === 'explore' ? 'is-selected' : ''} aria-pressed={mode === 'explore'} title="科普：逐步解释、图形引导" onClick={() => onMode('explore')}>科普</button>
      </div>
      <div className="nt-sidebar-utilities">
        <button type="button" onClick={mode === 'research' ? onTour : onGuide} title="使用方法"><CircleHelp size={17} /><span>帮助</span></button>
        <button type="button" onClick={onShortcuts} title="快捷键"><Keyboard size={17} /><span>快捷键</span></button>
        <button type="button" onClick={onStage} title="3 分钟演示"><MonitorPlay size={17} /><span>演示</span></button>
        <button type="button" onClick={onTheme} title={theme === 'light' ? '深色主题' : '亮色主题'}>{theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}<span>主题</span></button>
      </div>
    </div>
  </aside>
}
