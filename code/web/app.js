'use strict';

const $ = id => document.getElementById(id);
const keys = ['tst', 'sol', 'waso', 'n3_percentage', 'rem_percentage', 'n3_latency_aasm', 'sleep_efficiency'];
const advancedKeys = ['n3_percentage', 'rem_percentage', 'n3_latency_aasm'];
const state = {config: null, connected: false, mode: 'record', example: false, actual: null,
  actualPrevious: null, latest: null, dirty: false, revision: 0, epoch: 0, controller: null};
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => Math.abs(Number(value)) >= 1e6 ? Number(value).toExponential(2) : Number(value).toLocaleString('zh-CN', {maximumFractionDigits: 1});
const signed = value => `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}`;
const label = key => state.config?.fields.find(f => f.key === key)?.label || key;

async function connect() {
  $('connection-text').textContent = '正在连接';
  $('connection').className = 'connection';
  try {
    const [health, config] = await Promise.all([
      fetch('/api/health', {signal: AbortSignal.timeout(6000)}),
      fetch('/api/config', {signal: AbortSignal.timeout(6000)})
    ]);
    if (!health.ok || !config.ok) throw new Error('服务未就绪');
    state.config = await config.json();
    state.connected = true;
    $('connection').className = 'connection ready';
    $('connection-text').textContent = '评估服务已连接';
    $('connection').title = '点击重新检查连接';
    updateInputState();
    return true;
  } catch {
    state.connected = false;
    $('connection').className = 'connection offline';
    $('connection-text').textContent = '连接未就绪 · 重试';
    $('connection').title = '服务暂未就绪，请稍后点击重试';
    return false;
  }
}

function fieldSpec(key) {
  return state.config?.fields.find(f => f.key === key) || {
    key, min: 0, max: ['n3_percentage', 'rem_percentage', 'sleep_efficiency'].includes(key) ? 100 : undefined,
    exclusive_min: ['tst', 'sleep_efficiency'].includes(key)
  };
}

function readInputs() {
  const inputs = {}, errors = {};
  for (const key of keys) {
    const input = $(key), raw = input.value.trim(), spec = fieldSpec(key);
    if (input.validity.badInput) { errors[key] = '请填写有效数字，或留空表示未提供'; continue; }
    if (!raw) continue;
    const value = Number(raw);
    if (!Number.isFinite(value)) errors[key] = '请填写有效数字';
    else if (value < 0 || (spec.exclusive_min && value === 0)) errors[key] = spec.exclusive_min ? '请填写大于 0 的数值' : '数值不能小于 0';
    else if (spec.max !== undefined && value > spec.max) errors[key] = '百分比不能超过 100';
    else inputs[key] = value;
  }
  if ((inputs.n3_percentage || 0) + (inputs.rem_percentage || 0) > 100) {
    errors.n3_percentage = errors.rem_percentage = '深睡与 REM 占比相加不能超过 100%';
  }
  return {inputs, errors};
}

function showFieldError(key, message) {
  if (!$(key)) return;
  $(key).setAttribute('aria-invalid', message ? 'true' : 'false');
  $(`${key}-error`).textContent = message || '';
  $(`${key}-error`).hidden = !message;
}

function clearErrors() {
  keys.forEach(key => showFieldError(key, ''));
  $('form-error').hidden = true;
  $('form-error').textContent = '';
}

function showErrors(errors, message = '请检查标出的输入后再评估。') {
  clearErrors();
  Object.entries(errors).forEach(([key, error]) => showFieldError(key, error));
  $('form-error').textContent = errors._form || message;
  $('form-error').hidden = false;
  const first = keys.find(key => errors[key]);
  if (first) {
    if (advancedKeys.includes(first)) $('advanced').open = true;
    $(first).focus();
  } else $('form-error').focus();
}

function updateInputState() {
  const {inputs, errors} = readInputs();
  const valid = Object.keys(inputs).filter(key => !errors[key]);
  $('input-count').textContent = `${valid.length} / 7 项`;
  $('input-progress').style.width = `${valid.length / 7 * 100}%`;
  const advancedCount = advancedKeys.filter(key => valid.includes(key)).length;
  $('advanced-count').textContent = advancedCount ? `已填 ${advancedCount} / 3` : '可选 +3';
  $('fill-note').textContent = valid.length === 7 ? '七项已填齐，可生成完整输入评估。' :
    valid.length ? `已提供 ${valid.length} 项，未提供的指标按训练典型值填补。` : '至少填写一项；三至四项可提供更多信息。';
  if (inputs.tst !== undefined && !errors.tst) {
    const totalMinutes = Math.round(inputs.tst), hours = Math.floor(totalMinutes / 60), minutes = totalMinutes % 60;
    $('tst-help').textContent = inputs.tst > 1440 ? '数值超过 24 小时，请检查是否按分钟填写。' : `约 ${hours} 小时 ${minutes} 分钟，确认不含清醒时间。`;
  } else $('tst-help').textContent = '实际睡着的累计时长，不含清醒时间。';
  $('stale-note').hidden = !(state.latest && state.dirty);
  $('stale-note').textContent = state.mode === 'simulation' ?
    '模拟输入尚未评估。当前展示的是上一次结果，生成模拟评估后查看变化。' :
    '输入已修改。当前结果来自上一次评估，请重新生成。';
}

function setBusy(busy) {
  $('evaluate-button').disabled = busy;
  $('sleep-form').setAttribute('aria-busy', String(busy));
  $('evaluate-label').textContent = busy ? '正在生成评估…' : state.mode === 'simulation' ? '生成模拟评估' : '生成睡眠评估';
}

function fillValues(values) { keys.forEach(key => { $(key).value = values[key] ?? ''; }); }

function clearRecord() {
  state.epoch++;
  state.controller?.abort();
  Object.assign(state, {mode: 'record', example: false, actual: null, actualPrevious: null, latest: null, dirty: false, controller: null});
  state.revision++;
  fillValues({});
  clearErrors();
  $('example-note').hidden = true;
  $('simulation-note').hidden = true;
  $('record-mode').setAttribute('aria-pressed', 'true');
  $('simulation-mode').setAttribute('aria-pressed', 'false');
  $('simulation-mode').disabled = true;
  $('advanced').open = false;
  $('empty-state').hidden = false;
  $('result-content').hidden = true;
  $('result-badge').textContent = '等待记录';
  $('result-badge').className = 'muted-badge';
  $('raw-result').hidden = true;
  $('copy-status').textContent = '';
  setBusy(false);
  updateInputState();
}

async function loadPreset(name, autoEvaluate = false) {
  if (!state.connected && !(await connect())) {
    showErrors({_form: '评估服务未连接，请稍后点击右上角重试。'});
    return;
  }
  clearRecord();
  fillValues(state.config.presets[name]);
  state.example = true;
  state.revision++;
  $('example-note').hidden = false;
  $('advanced').open = name === 'full';
  updateInputState();
  if (autoEvaluate) await evaluate(); else $('tst').focus();
}

function setMode(mode) {
  if (state.controller || mode === state.mode) return;
  if (mode === 'simulation' && !state.actual) return;
  state.mode = mode;
  state.revision++;
  clearErrors();
  $('record-mode').setAttribute('aria-pressed', String(mode === 'record'));
  $('simulation-mode').setAttribute('aria-pressed', String(mode === 'simulation'));
  $('simulation-note').hidden = mode !== 'simulation';
  if (state.actual) {
    fillValues(state.actual.result.inputs);
    state.example = state.actual.example;
    $('example-note').hidden = !state.example;
    if (mode === 'record') {
      state.latest = state.actual;
      state.dirty = false;
      renderResult(state.actual, state.actualPrevious);
    } else state.dirty = true;
  }
  setBusy(false);
  updateInputState();
}

async function evaluate() {
  if (state.controller) return;
  clearErrors();
  const {inputs, errors} = readInputs();
  if (Object.keys(errors).length) {showErrors(errors); return;}
  if (!Object.keys(inputs).length) {showErrors({_form: '请至少填写一项睡眠指标；不知道的指标可以留空。'}); return;}
  if (!state.connected && !(await connect())) {showErrors({_form: '评估服务未连接，请稍后重试。'}); return;}
  const epoch = ++state.epoch, revision = state.revision, mode = state.mode, example = state.example;
  const controller = new AbortController();
  state.controller = controller;
  const timeout = setTimeout(() => controller.abort(), 15000);
  setBusy(true);
  try {
    const response = await fetch('/api/predict', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({inputs, mode}), signal: controller.signal});
    const result = await response.json();
    if (epoch !== state.epoch) return;
    if (!response.ok) {
      showErrors(result.errors || {_form: result.message || '输入未通过检查，请核对数值后重试。'});
      return;
    }
    const snapshot = {result, example, time: new Date()};
    let comparisonBase;
    if (mode === 'record') {
      comparisonBase = state.actual;
      state.actualPrevious = state.actual;
      state.actual = snapshot;
      $('simulation-mode').disabled = false;
      $('simulation-mode').title = '以最近一次记录为参考，探索模型输出变化';
    } else comparisonBase = state.actual;
    state.latest = snapshot;
    state.dirty = revision !== state.revision;
    renderResult(snapshot, comparisonBase);
    updateInputState();
    if (window.innerWidth <= 760) $('result-title').scrollIntoView({behavior: 'smooth', block: 'start'});
    $('result-title').focus({preventScroll: true});
  } catch (error) {
    if (epoch !== state.epoch) return;
    showErrors({_form: error.name === 'AbortError' ? '评估超时，请稍后重试。' : '无法连接评估服务，请检查服务是否仍在运行。'});
    if (error.name !== 'AbortError') {
      state.connected = false;
      $('connection').className = 'connection offline';
      $('connection-text').textContent = '连接未就绪 · 重试';
    }
  } finally {
    clearTimeout(timeout);
    if (epoch === state.epoch) {state.controller = null; setBusy(false);}
  }
}

function renderComparison(snapshot, base) {
  $('comparison').hidden = !base;
  if (!base) return;
  const simulated = snapshot.result.mode === 'simulation';
  const delta = Number((snapshot.result.score.value - base.result.score.value).toFixed(1));
  $('comparison-title').textContent = simulated ? '模拟结果与最近一次记录相比' : '与上次记录评估相比';
  $('comparison-delta').textContent = `${signed(delta)} 分`;
  const changed = keys.filter(key => snapshot.result.inputs[key] !== base.result.inputs[key]);
  const detail = changed.length ? `修改或补充了${changed.map(label).join('、')}。` : '输入没有变化，模型估计也保持一致。';
  $('comparison-detail').textContent = detail + (simulated ? '此变化不代表实际改善效果。' : '差异反映输入变化，不能单独用于判断睡眠是否改善。');
}

function renderResult(snapshot, base) {
  const r = snapshot.result;
  $('empty-state').hidden = true;
  $('result-content').hidden = false;
  const badge = r.mode === 'simulation' ? '模拟评估' : snapshot.example ? '示例评估' : '记录评估';
  $('result-badge').textContent = badge;
  $('result-badge').className = r.mode === 'simulation' ? 'muted-badge simulated' : 'muted-badge';
  $('score-value').textContent = r.score.value.toFixed(1);
  $('grade').textContent = r.score.grade;
  document.querySelector('.score-panel').dataset.grade = r.score.grade_code;
  $('score-arc').style.strokeDashoffset = String(477.522 * (1 - r.score.value / 100));
  $('scale-marker').style.left = `${r.score.value}%`;
  $('score-summary').textContent = r.mode === 'simulation' ? '根据调整后的输入生成。用于探索模型关系，请与真实记录区分。' :
    `按${snapshot.example ? '这组示例' : '本次'}输入，模型估计的睡眠体验落在「${r.score.grade}」区间。`;
  const timestamp = snapshot.time.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai'});
  $('evaluated-time').textContent = `${timestamp} · ${badge}`;
  renderComparison(snapshot, base);
  $('result-input-count').textContent = `${r.valid_input_count} / 7 项实填`;
  $('used-chips').innerHTML = r.used_features.map(key => `<span class="result-chip">${esc(label(key))} · ${esc(number(r.inputs[key]))}${esc(fieldSpec(key).unit || '')}</span>`).join('');
  $('missing-note').textContent = r.report.missing_note;
  $('limited-note').hidden = r.valid_input_count >= 3;
  $('evidence-text').textContent = r.reference.cv_mae == null ? '当前组合暂无历史误差参考。' :
    `同组合分组评估的平均绝对误差为 ${r.reference.cv_mae.toFixed(2)} 分，RMSE 为 ${r.reference.cv_rmse.toFixed(2)} 分（原始 GSQS 0–14 尺度）。`;
  const maxImpact = Math.max(.1, ...r.factors.map(f => Math.abs(f.score_contribution)));
  $('factor-list').innerHTML = r.factors.map(f => {
    const impact = Math.abs(f.score_contribution), width = impact / maxImpact * 46;
    const text = f.direction === 'neutral' ? '影响较小' : `${f.direction === 'up' ? '上调' : '下调'} ${impact.toFixed(1)} 分`;
    return `<div class="factor" data-factor="${esc(f.key)}"><div class="factor-header"><span class="factor-label">${esc(f.label)}<small>${esc(number(f.value))} ${esc(f.unit)}</small></span><span class="impact ${esc(f.direction)}">${text}</span></div><div class="factor-bar" aria-hidden="true"><span class="factor-bar-fill ${esc(f.direction)}" style="width:${width.toFixed(2)}%"></span></div><details><summary>为什么有这个影响？</summary><p>${esc(f.explanation)}</p><p>${esc(f.definition)}</p></details></div>`;
  }).join('');
  $('factor-note').textContent = r.score.clipped ? '展示分数已限制在 0–100；图中贡献基于限制前的指数，可能不会直接加总为页面分数。贡献是模型关联，不说明因果。' :
    '贡献相对“全部指标取训练典型值”的参考输入计算，表示模型中的关联，不说明某个指标造成了睡眠好坏。';
  $('report-summary').textContent = r.report.summary;
  $('report-drivers').innerHTML = r.report.drivers.map(text => `<p class="report-driver">${esc(text)}</p>`).join('') + `<p class="muted small">${esc(r.report.reference_note || '')}</p>`;
  $('next-steps').innerHTML = r.report.next_steps.map(step => `<li>${esc(step)}</li>`).join('');
  $('raw-result').hidden = false;
  $('raw-result').textContent = `本次原始 GSQS 连续估计：${r.prediction.toFixed(4)}。展示指数：${r.score.value.toFixed(1)} / 100。${r.score.clipped ? '原始预测超出量表范围，展示指数已限制到边界。' : ''}`;
  $('copy-status').textContent = '';
}

function reportText() {
  if (!state.latest) return '';
  const {result: r, example} = state.latest;
  return [`眠序 · ${r.mode === 'simulation' ? '模拟评估' : example ? '示例评估' : '记录评估'}`, r.report.summary,
    `睡眠体验指数：${r.score.value.toFixed(1)} / 100 · ${r.score.grade}`, '',
    r.report.missing_note, '', '后续操作：', ...r.report.next_steps,
    '', r.report.boundary_note, r.score.scale_note, '结果仅用于课程学习，不用于医疗诊断。'].join('\n');
}

async function copyReport() {
  const text = reportText();
  if (!text) return;
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else {
      const area = document.createElement('textarea');
      area.value = text; area.style.position = 'fixed'; area.style.opacity = '0';
      document.body.append(area); area.select();
      const success = document.execCommand('copy'); area.remove();
      if (!success) throw new Error('复制不可用');
    }
    $('copy-status').textContent = state.dirty ? '已复制上次生成的报告' : '报告已复制';
  } catch { $('copy-status').textContent = '浏览器未允许复制，请选中报告文字复制。'; }
}

$('sleep-form').addEventListener('submit', event => {event.preventDefault(); evaluate();});
keys.forEach(key => $(key).addEventListener('input', () => {
  state.revision++;
  if (state.latest) state.dirty = true;
  const {errors} = readInputs();
  showFieldError(key, errors[key]);
  for (const k of ['n3_percentage', 'rem_percentage']) showFieldError(k, errors[k]);
  $('form-error').hidden = true;
  updateInputState();
}));
document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => loadPreset(button.dataset.preset)));
$('hero-example').addEventListener('click', () => loadPreset('four', true));
$('empty-example').addEventListener('click', () => loadPreset('four', true));
$('clear-button').addEventListener('click', () => {clearRecord(); $('tst').focus();});
$('record-mode').addEventListener('click', () => setMode('record'));
$('simulation-mode').addEventListener('click', () => setMode('simulation'));
$('connection').addEventListener('click', connect);
$('copy-report').addEventListener('click', copyReport);
['about-button', 'score-help-button', 'footer-about'].forEach(id => $(id).addEventListener('click', () => $('about-dialog').showModal()));
['close-dialog', 'understood-button'].forEach(id => $(id).addEventListener('click', () => $('about-dialog').close()));
$('about-dialog').addEventListener('click', event => {if (event.target === $('about-dialog')) {const box = $('about-dialog').getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) $('about-dialog').close();}});
$('score-summary').setAttribute('aria-live', 'polite');
updateInputState();
connect();
