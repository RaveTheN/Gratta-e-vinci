const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'Griglia Rossa 5×5.html'), 'utf8');
const source = html.match(/<script id="mineLabEngine">([\s\S]*?)<\/script>/)[1];
const safe = [19,20,21,22,23,24];
const configs = () => Array.from({length:4}, (_,i) => ({name:'Laptop '+(i+1), capital:4000, stake:20}));
function make({players=configs(), target=600, sessionsPerDay=2, draw=k => new Set(k === 2 ? [0,1] : safe)} = {}) {
  const context = vm.createContext({pickRed:draw, eur:c => (c/100).toFixed(2)+' €'});
  const Constructor = vm.runInContext(source+'\nMineLab;', context);
  return new Constructor(players, target, sessionsPerDay);
}
function amounts(game, key) { return Array.from(game.pcs, pc => pc[key]); }
function conserved(game) {
  assert.equal(game.cash + game.committed - game.sessionCash, game.settled);
  for (const pc of game.pcs) {
    assert.equal(pc.cash, pc.capital + pc.wins * (pc.stake/10*18) - pc.total * pc.stake);
    assert.ok(Number.isSafeInteger(pc.cash) && pc.cash >= 0);
  }
}

test('each laptop reserves its own stake and draws a separate complete board', () => {
  let boards = 0;
  const game = make({draw:k => { if (k === 6) boards++; return new Set(k === 2 ? [0,1] : safe); }});
  game.start(); game.advance(0);
  assert.equal(boards, 4);
  assert.deepEqual(amounts(game,'cash'), [3980,3980,3980,3980]);
  assert.equal(game.committed, 80);
  assert.equal(new Set(game.pcs.map(pc => pc.mines)).size, 4);
  assert.ok(game.pcs.every(pc => pc.opened.size === 0));
  conserved(game);
  game.advance(6);
  assert.deepEqual(amounts(game,'cash'), [4016,4016,4016,4016]);
  assert.equal(game.committed, 0);
  conserved(game);
});

test('a mine on either selected cell loses exactly the stake at the correct time', () => {
  for (const [cell, seconds] of [[0,3],[1,5]]) {
    const game = make({draw:k => new Set(k === 2 ? [0,1] : [cell,19,20,21,22,23])});
    game.start(); game.advance(seconds);
    assert.deepEqual(amounts(game,'cash'), [3980,3980,3980,3980]);
    assert.deepEqual(amounts(game,'losses'), [1,1,1,1]);
    assert.equal(game.committed, 0);
    conserved(game);
  }
});

test('insufficient balances cannot borrow or reduce the configured stake', () => {
  const players = [0,19,20,4000].map((capital,i) => ({name:'PC '+i, capital, stake:20}));
  const game = make({players});
  game.start(); game.advance(0); game.stop(); game.advance(6);
  assert.equal(game.phase, 'paused');
  assert.deepEqual(amounts(game,'total'), [0,0,1,1]);
  assert.deepEqual(amounts(game,'cash'), [0,19,36,4016]);
  assert.deepEqual(amounts(game,'minimum'), [0,19,0,3980]);
  assert.deepEqual(amounts(game,'stake'), [20,20,20,20]);
  conserved(game);
});

test('the group target reserves all pending stakes and drains open games on stop', () => {
  const game = make();
  game.start(); game.advance(68); game.stop();
  const total = amounts(game,'total');
  assert.equal(game.phase, 'draining');
  assert.equal(game.committed, 80);
  game.advance(1);
  assert.equal(game.phase, 'paused');
  assert.equal(game.history.length, 1);
  assert.equal(game.history[0].reason, 'target');
  assert.equal(game.history[0].profit, 640);
  assert.deepEqual(amounts(game,'total'), total);
  assert.equal(game.committed, 0);
  assert.equal(game.session, 2);
  assert.equal(game.sessionCash, 16640);
  conserved(game);
});

test('pausing and resuming never moves time backwards or resets session money', () => {
  const game = make({draw:k => new Set(k === 2 ? [0,1] : (++boards % 2 ? [0,19,20,21,22,23] : safe))});
  let boards = 0;
  game.start(); game.advance(1); game.stop(); game.advance(10);
  assert.equal(game.phase, 'paused');
  assert.equal(game.now, 6);
  assert.equal(game.sessionCash, 16000);
  assert.equal(game.history.length, 0);
  const cash = game.cash;
  game.advance(1000);
  assert.equal(game.now, 6);
  assert.equal(game.cash, cash);
  game.start(); game.advance(0);
  assert.equal(game.now, 6);
  assert.equal(game.sessionCash, 16000);
  conserved(game);
});

test('start permissions at the daily deadline never depend on future results', () => {
  for (const won of [true,false]) {
    const game = make({draw:k => new Set(k === 2 ? [0,1] : won ? safe : [0,19,20,21,22,23])});
    game.dayStart = -43198; // Two seconds left in today's shared start budget.
    game.start(); game.advance(2);
    assert.equal(game.reason, 'time');
    assert.deepEqual(amounts(game,'total'), [1,1,1,1]);
    assert.equal(game.cash, 15920);
    game.stop(); game.advance(10);
    assert.equal(game.phase, 'paused');
    assert.equal(game.history[0].reason, 'time');
    assert.equal(game.history[1].reason, 'skipped');
    assert.deepEqual(amounts(game,'total'), [1,1,1,1]);
    assert.equal(game.cash, won ? 16064 : 15920);
    conserved(game);
  }
});

test('second session starts from a losing first and receives only remaining daily time', () => {
  let game;
  const counts = new Map();
  game = make({draw:k => {
    if (k === 2) return new Set([0,1]);
    const key = game.day+':'+game.session;
    const count = counts.get(key) || 0;
    counts.set(key, count+1);
    return new Set(Math.floor(count/4)%9 < 4 ? [0,19,20,21,22,23] : safe);
  }});
  game.start(); game.advance(24438);
  assert.equal(game.history.length, 1);
  assert.equal(game.history[0].reason, 'cap');
  assert.equal(game.history[0].profit, -320);
  assert.equal(game.session, 2);
  assert.equal(game.sessionCash, 15680);
  assert.equal(game.deadline - game.now, 18762);
  assert.equal(game.target, 600);
  conserved(game);
});

test('30 days carry every balance across two sessions without refills', () => {
  const game = make();
  game.start(); game.advance(10000);
  assert.equal(game.phase, 'done');
  assert.equal(game.history.length, 60);
  assert.equal(game.days.length, 30);
  assert.ok(game.history.every(row => row.reason === 'target' && row.profit === 640));
  assert.deepEqual(amounts(game,'cash'), [13600,13600,13600,13600]);
  assert.deepEqual(amounts(game,'total'), [600,600,600,600]);
  assert.equal(game.now, 4140);
  assert.equal(game.cash-game.initialCash, game.history.reduce((sum,row) => sum+row.profit,0));
  conserved(game);
});

test('one or three sessions per day retain automatic 30-day execution', () => {
  for (const sessionsPerDay of [1,3]) {
    const game = make({sessionsPerDay});
    game.start(); game.advance(10000);
    assert.equal(game.phase, 'done');
    assert.equal(game.history.length, 30*sessionsPerDay);
    assert.equal(game.days.length, 30);
    assert.ok(game.history.every(row => row.reason === 'target' && row.profit === 640));
    assert.ok(game.days.every(row => row.profit === 640*sessionsPerDay));
    for (let day = 1; day <= 30; day++) {
      assert.deepEqual(Array.from(game.history.filter(row => row.day === day), row => row.session),
        Array.from({length:sessionsPerDay}, (_,i) => i+1));
    }
    assert.deepEqual(amounts(game,'total'), Array(4).fill(300*sessionsPerDay));
    assert.equal(game.cash-game.initialCash, game.history.reduce((sum,row) => sum+row.profit,0));
    conserved(game);
  }
});

test('a daily deadline records every remaining configured session as skipped', () => {
  const game = make({sessionsPerDay:3});
  game.autoContinue = false;
  game.dayStart = -43198;
  game.start(); game.advance(100);
  assert.equal(game.phase, 'dayEnd');
  assert.equal(game.day, 1);
  assert.deepEqual(Array.from(game.history, row => row.reason), ['time','skipped','skipped']);
  assert.deepEqual(Array.from(game.history, row => row.session), [1,2,3]);
  assert.equal(game.days.length, 1);
  assert.deepEqual(amounts(game,'total'), [1,1,1,1]);
  conserved(game);
});

test('500 EUR drawdown does not protect 160 EUR and empty days consume no activity', () => {
  const game = make({draw:k => new Set(k === 2 ? [0,1] : [0,19,20,21,22,23])});
  game.start(); game.advance(5000);
  assert.equal(game.phase, 'done');
  assert.equal(game.cash, 0);
  assert.equal(game.now, 998);
  assert.equal(game.history.length, 60);
  assert.ok(game.history.every(row => row.reason === 'funds'));
  assert.deepEqual(amounts(game,'total'), [200,200,200,200]);
  conserved(game);
});

test('invalid money is rejected and heterogeneous stakes are conserved', () => {
  for (const target of [0,-1,6.5,NaN]) assert.throws(() => make({target}));
  for (const stake of [0,9,15,20.5]) assert.throws(() => make({players:[{capital:4000,stake}]}));
  const game = make({players:[{name:'A',capital:4000,stake:10},{name:'B',capital:7000,stake:30}]});
  game.start(); game.advance(6); game.stop();
  assert.deepEqual(amounts(game,'cash'), [4008,7024]);
  conserved(game);
});

test('sessions per day must be a positive safe integer', () => {
  for (const sessionsPerDay of [0,-1,1.5,1001,NaN,Infinity,'2',Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(() => make({sessionsPerDay}));
  }
});

test('next-day count changes apply to the next day and invalid counts leave state untouched', () => {
  const game = make({sessionsPerDay:1});
  game.autoContinue = false;
  game.start(); game.advance(1000);
  assert.equal(game.phase, 'dayEnd');
  const completed = JSON.stringify(game);
  for (const sessionsPerDay of [0,1.5,1001]) {
    assert.throws(() => game.nextDay(sessionsPerDay));
    assert.equal(JSON.stringify(game), completed);
  }
  game.nextDay(3);
  assert.equal(game.day, 2);
  assert.equal(game.sessionsPerDay, 3);
  assert.equal(game.history.length, 1);
  for (let session = 1; session <= 3; session++) {
    assert.equal(game.session, session);
    game.start(); game.advance(1000);
    assert.equal(game.phase, session === 3 ? 'dayEnd' : 'waiting');
  }
  assert.deepEqual(Array.from(game.history, row => row.day+':'+row.session), ['1:1','2:1','2:2','2:3']);
  assert.equal(game.days.length, 2);
  conserved(game);
});

test('a first animation timestamp before the click cannot advance negative time', () => {
  const frame = html.match(/function labAnimate\(at\) \{[\s\S]*?\n\}/)[0];
  const steps = [];
  vm.runInNewContext(frame+'\nlabAnimate(100);', {
    lab:{lastFrame:101, run:{advance:seconds => steps.push(seconds), phase:'paused'}},
    $:() => ({value:'10'}), labRender:() => {}
  });
  assert.deepEqual(steps, [0]);
});

test('manual mode waits between sessions and for the master to advance the day', () => {
  const game = make();
  game.autoContinue = false;
  game.start(); game.advance(100000);
  assert.equal(game.phase, 'waiting');
  assert.equal(game.history.length, 1);
  assert.equal(game.history[0].profit, 640);
  assert.equal(game.committed, 0);
  assert.deepEqual(amounts(game,'total'), [10,10,10,10]);
  const cash = game.cash;
  game.advance(100000);
  assert.equal(game.cash, cash);
  game.start(); game.advance(100000);
  assert.equal(game.phase, 'dayEnd');
  assert.equal(game.history.length, 2);
  assert.equal(game.days.length, 1);
  assert.equal(game.day, 1);
  const totals = amounts(game,'total');
  const lastCash = game.cash;
  const lastTime = game.now;
  game.start(); game.advance(100000);
  assert.equal(game.phase, 'dayEnd');
  assert.equal(game.cash, lastCash);
  assert.equal(game.now, lastTime);
  game.nextDay();
  assert.equal(game.day, 2);
  assert.equal(game.session, 1);
  assert.equal(game.phase, 'waiting');
  assert.equal(game.history.length, 2);
  assert.equal(game.days.length, 1);
  assert.equal(game.cash, lastCash);
  assert.equal(game.now, lastTime);
  assert.equal(game.dayStart, lastTime);
  assert.deepEqual(amounts(game,'total'), totals);
  assert.equal(game.sessionCash, 17280);
  conserved(game);
});

test('manual next day refuses running and draining games, then closes a paused partial session once', () => {
  const game = make({sessionsPerDay:3});
  game.autoContinue = false;
  game.start(); game.advance(0);
  const reserved = game.cash;
  game.nextDay();
  assert.equal(game.phase, 'running');
  assert.equal(game.day, 1);
  assert.equal(game.cash, reserved);
  assert.equal(game.history.length, 0);
  game.stop();
  game.nextDay();
  assert.equal(game.phase, 'draining');
  assert.equal(game.day, 1);
  assert.equal(game.committed, 80);
  assert.equal(game.history.length, 0);
  game.advance(10);
  assert.equal(game.phase, 'paused');
  const settledCash = game.cash;
  const totals = amounts(game,'total');
  const now = game.now;
  game.nextDay();
  assert.equal(game.day, 2);
  assert.equal(game.session, 1);
  assert.equal(game.phase, 'waiting');
  assert.equal(game.history.length, 1);
  assert.equal(game.history[0].day, 1);
  assert.equal(game.history[0].session, 1);
  assert.equal(game.history[0].reason, 'manual_day');
  assert.equal(game.history[0].profit, settledCash-game.initialCash);
  assert.equal(game.days.length, 1);
  assert.equal(game.days[0].profit, settledCash-game.initialCash);
  assert.equal(game.days[0].seconds, now);
  assert.equal(game.cash, settledCash);
  assert.equal(game.now, now);
  assert.equal(game.sessionCash, settledCash);
  assert.deepEqual(amounts(game,'total'), totals);
  conserved(game);
  game.nextDay();
  assert.equal(game.day, 3);
  assert.equal(game.history.length, 1);
  assert.equal(game.days.length, 2);
  assert.equal(game.days[1].profit, 0);
  assert.equal(game.cash, settledCash);
});

test('advancing a day before any play does not manufacture a session result', () => {
  const game = make({sessionsPerDay:3});
  game.autoContinue = false;
  game.nextDay();
  assert.equal(game.day, 2);
  assert.equal(game.history.length, 0);
  assert.equal(game.days.length, 1);
  assert.equal(game.days[0].profit, 0);
  assert.equal(game.days[0].seconds, 0);
  assert.equal(game.cash, game.initialCash);
  assert.deepEqual(amounts(game,'total'), [0,0,0,0]);
  conserved(game);
});

test('the last manual day completes the month without creating day 31', () => {
  const game = make({sessionsPerDay:1});
  game.autoContinue = false;
  for (let day = 1; day <= 30; day++) {
    assert.equal(game.day, day);
    game.start(); game.advance(10000);
    assert.equal(game.history.length, day);
    assert.equal(game.days.length, day);
    assert.equal(game.phase, day === 30 ? 'done' : 'dayEnd');
    if (day < 30) game.nextDay();
  }
  const cash = game.cash;
  game.nextDay(); game.start(); game.advance(10000);
  assert.equal(game.day, 30);
  assert.equal(game.phase, 'done');
  assert.equal(game.cash, cash);
  assert.equal(game.history.length, 30);
  assert.equal(game.days.length, 30);
  conserved(game);
});

function uiFunction(name) {
  return html.match(new RegExp('function '+name+'\\([^]*?\\n\\}'))[0];
}
function bulkUI() {
  const lab = {run:null, archives:[], configs:configs(), cards:configs().map((c,i) => ({
    name:{value:' Custom '+(i+1)+' '}, capital:{value:String(c.capital/100)}, stake:{value:String(c.stake/100)}
  }))};
  const nodes = {labGroupCapital:{value:'60,25'}, labGroupStake:{value:'0,30'}, labTarget:{value:'6'}, labSessions:{value:'3'}};
  const errors = [];
  let builds = 0;
  const apply = vm.runInNewContext(source+'\n'+['labMoney','labRead','labApplyAll'].map(uiFunction).join('\n')+'\nlabApplyAll;', {
    lab, $:id => nodes[id], labBuild:() => builds++, labError:error => errors.push(error)
  });
  return {lab, nodes, errors, apply, get builds() { return builds; }};
}

test('bulk controls update every initial capital and stake while preserving edited laptop names', () => {
  const ui = bulkUI();
  ui.apply();
  assert.deepEqual(Array.from(ui.lab.configs, c => ({...c})), Array.from({length:4}, (_,i) => ({
    name:'Custom '+(i+1), capital:6025, stake:30
  })));
  assert.equal(ui.builds, 1);
  assert.equal(ui.errors.at(-1), null);
  assert.equal(ui.lab.run, null);
});

test('bulk validation is atomic for invalid amounts, target and sessions', () => {
  for (const [field,value] of [['labGroupCapital','-1'],['labGroupStake','0,15'],['labGroupStake','0'],['labTarget','0'],['labSessions','1001']]) {
    const ui = bulkUI();
    const original = ui.lab.configs;
    ui.nodes[field].value = value;
    ui.apply();
    assert.equal(ui.lab.configs, original);
    assert.equal(ui.lab.run, null);
    assert.equal(ui.builds, 0);
    assert.ok(ui.errors.at(-1) instanceof Error || ui.errors.at(-1)?.message);
  }
});

test('bulk controls cannot overwrite balances or configuration after the experiment starts', () => {
  const ui = bulkUI();
  const run = ui.lab.run = make();
  run.start(); run.advance(0);
  const original = ui.lab.configs;
  const current = JSON.stringify(run);
  ui.apply();
  assert.equal(ui.lab.configs, original);
  assert.equal(ui.lab.run, run);
  assert.equal(JSON.stringify(run), current);
  assert.equal(ui.builds, 0);
  assert.equal(ui.errors.length, 0);
});

test('valid bulk values replace invalid individual amounts without changing archived history', () => {
  const ui = bulkUI();
  const archives = ui.lab.archives;
  archives.push({history:[{profit:640}]});
  ui.lab.cards[0].capital.value = 'invalid';
  ui.lab.cards[1].stake.value = '0,123';
  ui.apply();
  assert.equal(ui.builds, 1);
  assert.ok(ui.lab.configs.every(config => config.capital === 6025 && config.stake === 30));
  assert.equal(ui.lab.archives, archives);
  assert.equal(archives[0].history[0].profit, 640);
});

function renderUI(run) {
  const lab = {run, configs:configs(), cards:[], historyLength:-1};
  const nodes = {};
  const $ = id => nodes[id] ||= {value:id === 'labSessions' ? String(run.sessionsPerDay) : '6', replaceChildren(...children) { this.children = children; }};
  const render = vm.runInNewContext(['labMoney','labDuration','labSigned','labText','labHistoryLine','labRender'].map(uiFunction).join('\n')+'\nlabRender;', {
    lab, $, eur:c => (c/100).toFixed(2)+' EUR', document:{createElement:() => ({})}
  });
  return {lab, $, render};
}

test('manual day-end controls require next day and rendering a fresh empty day is safe', () => {
  const run = make({sessionsPerDay:1});
  run.autoContinue = false;
  run.start(); run.advance(1000);
  const {lab, $, render} = renderUI(run);
  render();
  assert.equal($('labStart').disabled, true);
  assert.equal($('labNextDay').disabled, false);
  assert.match($('labState').textContent, /Giorno 1\/30/);
  run.nextDay();
  render();
  assert.equal($('labStart').disabled, false);
  assert.match($('labState').textContent, /Giorno 2\/30/);
  lab.run = make({sessionsPerDay:1});
  lab.run.autoContinue = false;
  lab.run.nextDay();
  assert.equal(lab.run.history.length, 0);
  render();
  assert.equal($('labStart').disabled, false);
  assert.equal($('labProfit').textContent, '0.00 EUR');
  $('labSessions').value = '3';
  render();
  assert.match($('labPlan').textContent, /^3 sessioni/);
});

test('the last played session profit remains visible after the deadline skips later slots', () => {
  const run = make({sessionsPerDay:3});
  run.autoContinue = false;
  run.dayStart = -43198;
  run.start(); run.advance(10);
  assert.deepEqual(Array.from(run.history, entry => entry.reason), ['time','skipped','skipped']);
  const {$, render} = renderUI(run);
  render();
  assert.equal($('labProfit').textContent, '+0.64 EUR');
  assert.equal($('labHistory').children.length, 1);
  assert.match($('labHistory').children[0].textContent, /limite di tempo/);
});

function resetUI(run) {
  const lab = {run, archives:[], frame:7};
  const calls = {build:0, render:0, cancel:[]};
  const reset = vm.runInNewContext(uiFunction('labResetExperiment')+'\nlabResetExperiment;', {
    lab, labError:() => {}, labBuild:() => calls.build++, labRenderArchives:() => calls.render++,
    cancelAnimationFrame:id => calls.cancel.push(id)
  });
  return {lab, calls, reset};
}

test('a new experiment archives independent copies of completed history and daily results', () => {
  const run = make({sessionsPerDay:1});
  run.autoContinue = false;
  run.start(); run.advance(1000);
  const ui = resetUI(run);
  ui.reset();
  const record = ui.lab.archives[0];
  assert.equal(ui.lab.run, null);
  assert.equal(ui.lab.frame, null);
  assert.equal(ui.calls.build, 1);
  assert.equal(ui.calls.render, 1);
  assert.deepEqual(ui.calls.cancel, [7]);
  assert.equal(record.initialCash, 16000);
  assert.equal(record.cash, 16640);
  assert.equal(record.now, 69);
  assert.equal(record.history.length, 1);
  assert.equal(record.days.length, 1);
  assert.equal(record.history[0].profit, 640);
  assert.equal(record.days[0].profit, 640);
  run.history[0].profit = -1;
  run.days[0].profit = -1;
  assert.equal(record.history[0].profit, 640);
  assert.equal(record.days[0].profit, 640);
  ui.reset();
  assert.equal(ui.lab.archives.length, 1);
});

test('archiving a paused partial session preserves its result without rewriting the original history', () => {
  const run = make();
  run.autoContinue = false;
  run.start(); run.advance(0); run.stop(); run.advance(10);
  assert.equal(run.phase, 'paused');
  assert.equal(run.history.length, 0);
  const ui = resetUI(run);
  ui.reset();
  const record = ui.lab.archives[0];
  assert.equal(record.history.length, 1);
  assert.equal(record.history[0].reason, 'manual_end');
  assert.equal(record.history[0].profit, 64);
  assert.equal(record.cash-record.initialCash, record.history[0].profit);
  assert.equal(record.days.length, 1);
  assert.equal(record.days[0].profit, 64);
  assert.equal(record.days[0].seconds, 6);
  assert.equal(run.history.length, 0);
  assert.equal(run.days.length, 0);
});

test('a new experiment cannot clear an active run or unsettled stakes', () => {
  const run = make();
  run.start(); run.advance(0);
  const ui = resetUI(run);
  for (const phase of ['running','draining','paused']) {
    run.phase = phase;
    ui.reset();
    assert.equal(ui.lab.run, run);
    assert.equal(ui.lab.archives.length, 0);
    assert.equal(ui.calls.build, 0);
    assert.equal(ui.calls.render, 0);
    assert.deepEqual(ui.calls.cancel, []);
    assert.equal(run.committed, 80);
  }
});

test('the archive exposes complete session history and the retained result as text', () => {
  const nodes = {};
  const createElement = tag => ({tag, children:[], append(...children) { this.children.push(...children); }});
  const $ = id => nodes[id] ||= {replaceChildren(...children) { this.children = children; }};
  const lab = {archives:[{initialCash:16000, cash:16640, now:69, days:[{day:1}], history:[
    {day:1, session:1, profit:640, reason:'target'}, {day:1, session:2, profit:0, reason:'skipped'}
  ]}]};
  const render = vm.runInNewContext(['labDuration','labSigned','labHistoryLine','labRenderArchives'].map(uiFunction).join('\n')+'\nlabRenderArchives;', {
    lab, $, eur:c => (c/100).toFixed(2)+' EUR', document:{createElement}
  });
  render();
  assert.equal($('labArchive').hidden, false);
  const entry = $('labPastRuns').children[0];
  assert.equal(entry.tag, 'details');
  assert.match(entry.children[0].textContent, /Esperimento 1.*166.40 EUR.*\+6.40 EUR/);
  assert.match(entry.children[1].textContent, /G1 · S1: \+6.40 EUR · obiettivo/);
  assert.match(entry.children[1].textContent, /G1 · S2: 0.00 EUR · non avviata/);
});
