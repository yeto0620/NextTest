export const CONTROL_LABELS = {
  Cement: '水泥', BlastFurnaceSlag: '矿渣', FlyAsh: '粉煤灰', Water: '水',
  Superplasticizer: '减水剂', CoarseAggregate: '粗骨料', FineAggregate: '细骨料', Age: '龄期',
}
export const CONTROL_UNITS = { Age: 'day', default: 'kg/m³' }
export const STRATEGY_META = {
  greedy_prediction: { label: '预测优先', short: 'PREDICTION', copy: '先试模型估计最接近目标的配方。' },
  max_disagreement: { label: '分歧优先', short: 'DISAGREEMENT', copy: '先试树模型意见最不一致的配方。' },
  random: { label: '随机对照', short: 'RANDOM', copy: '用固定随机基线作对照。' },
}
export const STATUS_LABELS = {
  ready: '等待下一次建议', awaiting_user_confirmation: '建议已封存，等待确认',
  budget_exhausted: '预算已用完', candidate_pool_empty: '候选池已用完',
  release_uncertain: '释放状态不确定', update_uncertain: '更新状态不确定', update_failed: '模型更新失败',
  stopped: '需要人工核查',
}
export const STOP_STATUS = new Set(['release_uncertain', 'update_uncertain', 'update_failed'])

export function text(value) {
  return value == null || value === '' ? '—' : String(value)
}
export function number(value, places = 1) {
  return value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toFixed(places)
}
export function unitFor(key) { return CONTROL_UNITS[key] || CONTROL_UNITS.default }
export function controlEntries(controls = {}, includeAge = false) {
  return Object.entries(controls).filter(([key]) => includeAge || key !== 'Age')
}
export function statusLabel(value) { return STATUS_LABELS[value] || value || '—' }
export function strategyLabel(value) { return STRATEGY_META[value]?.label || value || '—' }
export function pct(value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(0)}%` : '—' }

export function rankCandidates(rows, strategy, goal = 'maximize') {
  if (!Array.isArray(rows)) return []
  const copy = [...rows]
  if (strategy === 'greedy_prediction') {
    return copy.sort((a, b) => (goal === 'maximize' ? b.prediction - a.prediction : a.prediction - b.prediction) || a.row_id.localeCompare(b.row_id))
  }
  if (strategy === 'max_disagreement') {
    return copy.sort((a, b) => ((b.disagreement ?? -1) - (a.disagreement ?? -1)) || a.row_id.localeCompare(b.row_id))
  }
  return copy.sort((a, b) => a.row_id.localeCompare(b.row_id))
}

export function comparePair(rows, selectedId, strategy, goal) {
  const ranked = rankCandidates(rows, strategy, goal)
  const selected = ranked.find(row => row.row_id === selectedId) || ranked[0]
  const differs = row => {
    if (!selected || row.row_id === selected.row_id) return false
    const keys = new Set([...Object.keys(selected.controls || {}), ...Object.keys(row.controls || {})])
    return [...keys].some(key => Number(selected.controls?.[key]) !== Number(row.controls?.[key]))
  }
  const other = ranked.find(differs) || ranked.find(row => row.row_id !== selected?.row_id)
  return [selected, other].filter(Boolean)
}

export function candidateState(id, view, selectedId, compareIds) {
  if (view?.pending?.row_id === id) return 'pending'
  if (view?.history?.some(item => item.row_id === id)) return 'revealed'
  if (selectedId === id) return 'selected'
  if (compareIds.includes(id)) return 'compare'
  return 'open'
}


export function reflectionDirection(prediction, observation) {
  if (!Number.isFinite(Number(prediction)) || !Number.isFinite(Number(observation))) return null
  const p = Number(prediction).toFixed(2)
  const o = Number(observation).toFixed(2)
  if (Number(o) > Number(p)) return 'higher'
  if (Number(o) < Number(p)) return 'lower'
  return 'close'
}

export function reflectionSentence(prediction, observation) {
  const direction = reflectionDirection(prediction, observation)
  if (direction === 'higher') return '本次历史实测高于封存预测。'
  if (direction === 'lower') return '本次历史实测低于封存预测。'
  if (direction === 'close') return '本次历史实测与封存预测接近。'
  return '本次结果尚不可比较。'
}

export function hypothesisLabel(hypothesis) {
  if (!hypothesis || hypothesis.skipped) return '未填写，不影响实验'
  if (hypothesis.choice === 'higher') return '结果可能高于预测'
  if (hypothesis.choice === 'close') return '结果接近预测'
  if (hypothesis.choice === 'lower') return '结果可能低于预测'
  return '未填写，不影响实验'
}
