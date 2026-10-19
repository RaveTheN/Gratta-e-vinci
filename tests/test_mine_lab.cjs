const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'Griglia Rossa 5×5.html'), 'utf8');
const source = html.match(/<script id="mineLabEngine">([\s\S]*?)<\/script>/)[1];
const safe = [19,20,21,22,23,24];
const configs = () => Array.from({length:4}, (_,i) => ({name:'Laptop '+(i+1), capital:4000, stake:20}));
function make({players=configs(), target=600, draw=k => new Set(k === 2 ? [0,1] : safe)} = {}) {
  const context = vm.createContext({pickRed:draw, eur:c => (c/100).toFixed(2)+' €'});
  const Constructor = vm.runInContext(source+'\nMineLab;', context);
  return new Constructor(players, target);
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

test('a first animation timestamp before the click cannot advance negative time', () => {
  const frame = html.match(/function labAnimate\(at\) \{[\s\S]*?\n\}/)[0];
  const steps = [];
  vm.runInNewContext(frame+'\nlabAnimate(100);', {
    lab:{lastFrame:101, run:{advance:seconds => steps.push(seconds), phase:'paused'}},
    $:() => ({value:'10'}), labRender:() => {}
  });
  assert.deepEqual(steps, [0]);
});

test('single-session mode stops the group and waits for the next master start', () => {
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
  assert.equal(game.phase, 'waiting');
  assert.equal(game.history.length, 2);
  assert.equal(game.days.length, 1);
  assert.equal(game.day, 2);
  assert.equal(game.sessionCash, 17280);
  conserved(game);
});
