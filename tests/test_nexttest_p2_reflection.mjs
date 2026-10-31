import test from 'node:test'
import assert from 'node:assert/strict'
import { reflectionDirection, reflectionSentence } from '../frontend/src/workbench/data.js'

test('reflection direction is deterministic at display precision', () => {
  assert.equal(reflectionDirection(62.02, 71.30), 'higher')
  assert.equal(reflectionDirection(62.02, 55.10), 'lower')
  assert.equal(reflectionDirection(62.02, 62.021), 'close')
  assert.equal(reflectionDirection(62.02, 62.024), 'close')
})

test('reflection sentences are fixed and do not claim strategy superiority', () => {
  assert.equal(reflectionSentence(62.02, 71.30), '本次历史实测高于封存预测。')
  assert.equal(reflectionSentence(62.02, 55.10), '本次历史实测低于封存预测。')
  assert.equal(reflectionSentence(62.02, 62.021), '本次历史实测与封存预测接近。')
})
