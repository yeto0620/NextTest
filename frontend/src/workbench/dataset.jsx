import React, { createContext, useContext } from 'react'

export const CONCRETE_META = {
  id: 'demo-concrete',
  displayName: 'UCI Concrete',
  shortId: '28D',
  localLabel: 'LOCAL DATASET',
  target: { key: 'CompressiveStrength', displayName: '抗压强度', unit: 'MPa' },
  features: [
    { key: 'Cement', displayName: '水泥', unit: 'kg/m³', role: 'control' },
    { key: 'BlastFurnaceSlag', displayName: '矿渣', unit: 'kg/m³', role: 'control' },
    { key: 'FlyAsh', displayName: '粉煤灰', unit: 'kg/m³', role: 'control' },
    { key: 'Water', displayName: '水', unit: 'kg/m³', role: 'control' },
    { key: 'Superplasticizer', displayName: '减水剂', unit: 'kg/m³', role: 'control' },
    { key: 'CoarseAggregate', displayName: '粗骨料', unit: 'kg/m³', role: 'control' },
    { key: 'FineAggregate', displayName: '细骨料', unit: 'kg/m³', role: 'control' },
    { key: 'Age', displayName: '龄期', unit: 'day', role: 'context' },
  ],
  isCustom: false,
}

export function metaFromView(view) {
  const dataset = view?.dataset
  if (!dataset) return CONCRETE_META
  const units = dataset.units || {}
  const features = (dataset.features || []).map(feature => ({
    key: feature.name,
    displayName: feature.display_name || feature.name,
    unit: feature.unit || units[feature.name] || '',
    role: feature.role,
  }))
  return {
    id: dataset.dataset_id || dataset.id || 'custom',
    displayName: dataset.display_name || dataset.displayName || 'Local dataset',
    shortId: dataset.short_id || (dataset.dataset_id ? String(dataset.dataset_id).slice(-8) : ''),
    localLabel: 'LOCAL DATASET',
    target: {
      key: dataset.target?.name || 'target',
      displayName: dataset.target?.display_name || dataset.target?.name || 'Target',
      unit: dataset.target?.unit || '',
    },
    features,
    units,
    isCustom: true,
    unitNotVerified: true,
    historicalReplay: true,
  }
}

const DatasetContext = createContext(CONCRETE_META)
export function DatasetMetaProvider({ meta, children }) { return <DatasetContext.Provider value={meta || CONCRETE_META}>{children}</DatasetContext.Provider> }
export function useDataset() { return useContext(DatasetContext) }
export function labelFor(meta, key) { return meta.features.find(item => item.key === key)?.displayName || key }
export function unitFor(meta, key) {
  if (key === meta.target.key) return meta.target.unit || 'unit not supplied'
  return meta.features.find(item => item.key === key)?.unit || 'unit not supplied'
}
export function targetUnit(meta) { return meta.target.unit || 'unit not supplied' }
export function featureKeys(meta) { return meta.features.map(item => item.key) }
export function featureRole(meta, key) { return meta.features.find(item => item.key === key)?.role || 'control' }
