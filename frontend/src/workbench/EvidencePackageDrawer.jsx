import React, { useEffect } from 'react'
import { CheckCircle2, Download, FileJson2, FileText, LoaderCircle, PackageCheck, ShieldCheck, X } from 'lucide-react'

function displayMetric(value) {
  return value == null ? '证据不足' : String(value)
}

export default function EvidencePackageDrawer({ open, onClose, busy, error, packageData, onMarkdown, onJson }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = event => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  const defense = packageData?.defense_brief
  const audit = packageData?.audit_public
  const snapshot = packageData?.snapshot_public
  return <div className="nt-package-layer" role="dialog" aria-modal="true" aria-labelledby="nt-package-title">
    <button type="button" className="nt-package-backdrop" onClick={onClose} aria-label="关闭成果包" />
    <aside className="nt-package-panel">
      <header className="nt-package-head"><div><span className="nt-kicker">VERIFIED PACKAGE / 只读导出</span><h2 id="nt-package-title">成果包</h2><p>只在服务端审计通过后生成；不含方案池或未公布标签。</p></div><button type="button" className="nt-icon-button" onClick={onClose} aria-label="关闭成果包"><X size={16} /></button></header>
      {busy && <div className="nt-package-loading"><LoaderCircle size={18} className="nt-spin" /><strong>正在核验并生成</strong><span>不写入项目、不重跑模型</span></div>}
      {!busy && error && <div className="nt-package-error"><ShieldCheck size={17} /><div><strong>成果包不可用</strong><p>{error}</p></div></div>}
      {!busy && packageData && <>
        <section className="nt-package-stamp"><PackageCheck size={19} /><div><span>PAYLOAD VERIFIED</span><strong>{defense?.evidence_status === 'available' ? '可导出' : '证据不足'}</strong></div><code>{packageData.payload_sha256?.slice(0, 16)}…</code></section>
        <section className="nt-package-metrics" aria-label="公开统计">
          <div><span>已公布</span><strong>{defense?.revealed_count ?? '—'}</strong><small>历史记录</small></div>
          <div><span>MAE</span><strong>{displayMetric(defense?.mae)}</strong><small>描述性统计</small></div>
          <div><span>最大误差</span><strong>{displayMetric(defense?.max_absolute_error)}</strong><small>描述性统计</small></div>
        </section>
        <section className="nt-package-brief"><span className="nt-kicker">DEFENSE BRIEF</span><p>{defense?.summary || '服务端没有提供可公开的答辩摘要。'}</p><dl><div><dt>项目</dt><dd>{packageData.project_id}</dd></div><div><dt>状态</dt><dd>{snapshot?.status || '—'}</dd></div><div><dt>审计</dt><dd>{audit?.status || '—'}</dd></div></dl></section>
        <section className="nt-package-boundaries"><span>导出包含</span><p><CheckCircle2 size={13} /> 已公布历史、公开审计摘要、确定性统计与科学边界。</p><span>导出不包含</span><p><ShieldCheck size={13} /> pending target、独立 test 标签、CSV、路径、环境变量与 API Key。</p></section>
        <div className="nt-package-actions"><button type="button" className="nt-secondary-button" onClick={onJson}><FileJson2 size={15} /> JSON</button><button type="button" className="nt-primary" onClick={onMarkdown}><FileText size={15} /> 下载 Markdown <Download size={14} /></button></div>
      </>}
      <footer>只读成果包 · 历史回放不是新实验</footer>
    </aside>
  </div>
}
