import React, { useEffect, useRef } from 'react'
import { Archive, Beaker, CircleHelp, GitCompareArrows, Keyboard, MessageCircleMore, Orbit, Radar, ScanSearch, X } from 'lucide-react'

const shortcuts = [
  ['1', '观测', ScanSearch, '打开实验首页'],
  ['2', '方案', Orbit, '打开方案空间'],
  ['3', '实验', Beaker, '打开实验台'],
  ['4', '证据', Radar, '打开证据链'],
  ['S', '策略', GitCompareArrows, '打开策略台'],
  ['A', '助手', MessageCircleMore, '解释公开证据'],
  ['L', '档案', Archive, '比较已核验项目'],
  ['?', '指南', CircleHelp, '打开使用方法'],
]

export default function WorkspaceShortcuts({ open, onClose, onNavigate, onStrategy, onGuide, onAssistant, onLibrary }) {
  const closeRef = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = event => { if (event.key === 'Escape') onClose() }
    const timer = window.setTimeout(() => closeRef.current?.focus(), 20)
    window.addEventListener('keydown', onKeyDown)
    return () => { window.clearTimeout(timer); window.removeEventListener('keydown', onKeyDown) }
  }, [open, onClose])
  if (!open) return null
  function run(key) {
    onClose()
    if (key === 'S') return onStrategy()
    if (key === 'A') return onAssistant()
    if (key === 'L') return onLibrary()
    if (key === '?') return onGuide()
    onNavigate({ 1: 'mission', 2: 'atlas', 3: 'bench', 4: 'trail' }[key])
  }
  return <aside className="nt-shortcut-dock" role="dialog" aria-modal="false" aria-labelledby="nt-shortcut-title">
    <header><span><Keyboard size={15} /> 工作区快捷键</span><button ref={closeRef} type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭快捷键"> <X size={14} /> </button></header>
    <div className="nt-shortcut-list">{shortcuts.map(([key, label, Icon, copy]) => <button type="button" key={key} onClick={() => run(key)}><Icon size={15} /><span><strong>{label}</strong><small>{copy}</small></span><kbd>{key}</kbd></button>)}</div>
    <footer>输入框、表格筛选和数值设置时不会占用快捷键。</footer>
  </aside>
}
