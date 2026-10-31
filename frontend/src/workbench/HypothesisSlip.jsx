import React from 'react'
import { Feather, Info, SkipForward } from 'lucide-react'

const OPTIONS = [
  ['higher', '结果可能高于预测', '实际强度可能比封存预测更高'],
  ['close', '结果接近预测', '实际强度大致落在预测附近'],
  ['lower', '结果可能低于预测', '实际强度可能比封存预测更低'],
]

export default function HypothesisSlip({ hypothesis, onChange, onSkip, locked, savedWithoutLocal, nextRound = false }) {
  const skipped = hypothesis?.skipped === true
  const choice = hypothesis?.choice || null
  const note = hypothesis?.note || ''
  return <section className={`nt-hypothesis ${locked ? 'is-locked' : ''}`} aria-labelledby="nt-hypothesis-title">
    <div className="nt-hypothesis-head">
      <div><span className="nt-kicker">{nextRound ? 'NEXT ROUND / 下一轮预判' : 'PRE-EXPERIMENT / 实验前预判'}</span><h3 id="nt-hypothesis-title">{nextRound ? '下一轮，你觉得结果会落在哪边？' : '你觉得结果会落在哪边？'}<small>可选，不参与模型计算</small></h3></div>
      {!locked && <button type="button" className="nt-link-button" onClick={onSkip}><SkipForward size={12} /> 跳过预判</button>}
    </div>
    {locked && savedWithoutLocal ? <div className="nt-hypothesis-missing"><Info size={13} /> 这条预判没有随项目保存；刷新或恢复后无法恢复个人判断。科研事实不受影响。</div> : <>
      <div className="nt-hypothesis-options" role="radiogroup" aria-label="实验前预判">
        {OPTIONS.map(([id, label, detail], index) => <button type="button" key={id} role="radio" aria-checked={choice === id} disabled={locked} className={choice === id ? 'is-selected' : ''} onClick={() => onChange({ choice: id, note, skipped: false })}>
          <span>{String(index + 1).padStart(2, '0')}</span><strong>{label}</strong><small>{detail}</small>
        </button>)}
      </div>
      <label className="nt-hypothesis-note"><span><Feather size={12} /> 可选短句：为什么这样猜？</span><textarea value={note} maxLength={120} disabled={locked} placeholder="例如：这次配方的水灰比看起来比已经试过的更低。" onChange={event => onChange({ choice, note: event.target.value, skipped: false })} /></label>
      <div className="nt-hypothesis-foot"><span>{note.length}/120 字</span><span>{nextRound ? '上一轮预判保留在下方 Reflection Card；本轮预判只用于下一次揭示。' : locked ? '已冻结在本次浏览器会话；不写入项目 API。' : skipped ? '已跳过；仍可锁定下一实验。' : '只存浏览器内存；刷新会丢失，不影响排序。'}</span></div>
    </>}
    {!locked && skipped && <p className="nt-hypothesis-skip"><Info size={12} /> 已跳过预判。核心流程仍可继续；揭示后只显示“未填写，不影响实验”。</p>}
    {locked && !savedWithoutLocal && !choice && skipped && <p className="nt-hypothesis-skip"><Info size={12} /> 你选择了跳过预判；这不影响实验，也不进入任何 API 请求。</p>}
    {locked && !savedWithoutLocal && !choice && !skipped && <p className="nt-hypothesis-skip"><Info size={12} /> 未填写预判。可以继续；揭示后只显示“未填写，不影响实验”。</p>}
  </section>
}
