import React from 'react'
import { ArrowDown, ArrowUp, Beaker, EyeOff, LockKeyhole, Sparkles } from 'lucide-react'
import { hypothesisLabel, number } from './data'
import { useDataset } from './dataset'

function clamp(value, min, max) { return Math.max(min, Math.min(max, value)) }

export default function EvidencePrism({ pending, last, hypothesis, transition, mode }) {
  const meta = useDataset()
  const unit = meta.target.unit || 'unit not supplied'
  const revealed = Boolean(last && Number.isFinite(Number(last.revealed_target)))
  const prediction = revealed ? last.prediction : pending?.prediction
  const observation = revealed ? last.revealed_target : null
  const error = revealed ? last.absolute_error : null
  const hasPrediction = Number.isFinite(Number(prediction))
  const low = hasPrediction ? Math.min(Number(prediction), revealed ? Number(observation) : Number(prediction)) - 5 : 0
  const high = hasPrediction ? Math.max(Number(prediction), revealed ? Number(observation) : Number(prediction)) + 5 : 1
  const position = value => hasPrediction ? clamp((Number(value) - low) / Math.max(high - low, 0.0001) * 100, 0, 100) : 0
  const hypothesisText = hypothesis == null ? '未随项目保存' : hypothesisLabel(hypothesis)
  return <section className={`nt-prism ${revealed ? 'is-revealed' : pending ? 'is-pending' : 'is-empty'} ${mode === 'research' ? 'is-research' : ''}`} aria-labelledby="nt-prism-title">
    <header className="nt-prism-head">
      <div><span className="nt-kicker">EVIDENCE PRISM / 一条判断如何变成证据</span><h3 id="nt-prism-title">我的预判 <span>→</span> 锁定预测 <span>→</span> 历史结果 <span>→</span> 判断更新</h3></div>
      <span className={`nt-prism-status ${revealed ? 'is-done' : ''}`}>{revealed ? '本轮完成' : pending ? '等待查看结果' : '尚未开始'}</span>
    </header>
    <div className="nt-prism-grid">
      <div className="nt-prism-col is-hypothesis">
        <span className="nt-prism-index">01 / 我的预判</span>
        <strong>{hypothesisText}</strong>
        <p>{hypothesis?.note ? `“${hypothesis.note}”` : hypothesis == null ? '本地预判没有随项目保存；不猜测、不补写。' : hypothesis?.skipped ? '你跳过了预判；它不影响实验，只用于查看结果后的个人反思。' : !hypothesis?.choice ? '未填写，不影响实验；它只用于查看结果后的个人反思。' : '这是你在锁定前写下的判断，不是科研证据。'}</p>
        <small>只存在浏览器内存</small>
      </div>
      <div className="nt-prism-col is-prediction">
        <span className="nt-prism-index">02 / 锁定预测</span>
        <strong>{number(prediction, 2)} <em>{unit}</em></strong>
        <div className="nt-prism-scale" aria-hidden="true"><span className="nt-prism-axis" /><i className="nt-prism-tick tick-prediction" style={{ left: `${position(prediction)}%` }} /><span className="nt-prism-axis-labels"><small>{number(low, 0)}</small><small>{number(high, 0)} {unit}</small></span></div>
        <p>{pending ? `预测已写入项目；方案 ${pending.row_id}` : revealed ? `当时保存的预测；方案 ${last.row_id}` : '点击“锁定当前预测”后，这里才会保存数值。'}</p>
        <small>{mode === 'research' && pending ? `模型分歧 ${number(pending.disagreement, 2)} ${unit}` : '不是实测值'}</small>
      </div>
      <div className="nt-prism-col is-observation">
        <span className="nt-prism-index">03 / 历史结果</span>
        {revealed ? <>
          <strong>{number(observation, 2)} <em>{unit}</em></strong>
          <div className="nt-prism-scale" aria-hidden="true"><span className="nt-prism-axis" /><i className="nt-prism-tick tick-observation" style={{ left: `${position(observation)}%` }} /><span className="nt-prism-error" style={{ left: `${Math.min(position(prediction), position(observation))}%`, width: `${Math.abs(position(observation) - position(prediction))}%` }} /></div>
          <p>绝对误差 <b>{number(error, 2)} {unit}</b>。这是一条历史记录，不是新做的实验。</p>
          <small>来自冻结历史回放</small>
        </> : <>
          <div className="nt-frost" aria-label="历史结果尚未查看"><EyeOff size={20} /><strong>尚未查看</strong><span>锁定预测前，历史结果不会进入页面</span></div>
          <p>锁定预测后，你可以人工确认查看这一条历史结果。</p>
          <small>遮蔽区域不包含历史答案</small>
        </>}
      </div>
      <div className="nt-prism-col is-update">
        <span className="nt-prism-index">04 / 判断更新</span>
        {revealed ? <>
          <strong>{transition?.after?.model_sha ? '模型已更新' : '等待模型版本记录'}</strong>
          <div className="nt-prism-delta">
            <span><LockKeyhole size={12} /> 查看前：{transition?.before?.observed_count ?? '—'} 训练 / {transition?.before?.remaining_budget ?? '—'} 次</span>
            <span><Sparkles size={12} /> 查看后：{transition?.after?.observed_count ?? '—'} 训练 / {transition?.after?.remaining_budget ?? '—'} 次</span>
          </div>
          {transition?.before?.model_sha && transition?.after?.model_sha && <p className="nt-prism-sha">{transition.before.model_sha.slice(0, 10)}… <ArrowDown size={11} /> {transition.after.model_sha.slice(0, 10)}…</p>}
          <small>{transition ? '模型、训练行数与预算已变化' : '模型前后版本不可用；不补造'}</small>
        </> : <><strong>等待证据</strong><p>查看结果后才显示模型版本、训练行数和剩余次数变化。</p><small>当前不显示预测性结论</small></>}
      </div>
    </div>
    <footer className="nt-prism-foot"><span>{revealed ? `结果 ${number(observation, 2)} − 预测 ${number(prediction, 2)} = ${number(Number(observation) - Number(prediction), 2)} ${unit}` : pending ? '预测已保存；等待人工确认查看结果' : '尚未锁定预测；历史结果保持隐藏'}</span><span><Beaker size={12} /> 历史回放 / 不是新实验</span></footer>
  </section>
}
