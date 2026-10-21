'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

test('a delayed status response cannot undo the master shutdown message',async()=>{
    const source=fs.readFileSync(path.resolve(__dirname,'../../Gratta e vinci Master/web/app.js'),'utf8');
    const end=source.indexOf("\ndocument.querySelectorAll('[data-action]').forEach");
    assert.ok(end>0);
    const elements=new Map();
    const buttons=['start','pause','resume','stop','emergency','shutdown'].map(action=>({dataset:{action}}));
    const document={querySelector(selector){
        if(!elements.has(selector))elements.set(selector,{textContent:''});
        return elements.get(selector);
    },querySelectorAll(){return buttons;}};
    let deliverStatus,requests=0;
    const paused={session:{status:'paused_manual'},controls:{help:'Pausa manuale: riaprire il master per riprendere.'}};
    const context=vm.createContext({document,clearInterval,crypto:{randomUUID:()=> 'command-id'},
        fetch:async url=>{
            requests++;
            if(url==='/api/status')return new Promise(resolve=>{deliverStatus=resolve;});
            assert.equal(url,'/api/command');
            return {ok:true,json:async()=>paused};
        }});
    vm.runInContext(source.slice(0,end),context);
    const lateRefresh=context.refresh();
    await context.command('shutdown');
    deliverStatus({ok:true,json:async()=>({session:{status:'active'},controls:{help:'Sessione in esecuzione'}})});
    await lateRefresh;
    await context.refresh();
    assert.equal(requests,2);
    assert.equal(elements.get('#connection').textContent,'Master in chiusura');
    assert.equal(elements.get('#phase').textContent,'In pausa · master chiuso');
    assert.equal(elements.get('#session-help').textContent,paused.controls.help);
    assert.match(elements.get('#notice').textContent,/Sessione conservata in pausa/);
    assert.ok(buttons.every(button=>button.disabled));
});
