'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const web=path.resolve(__dirname,'../../Gratta e vinci Master/web');
const source=fs.readFileSync(path.join(web,'app.js'),'utf8');

function dashboard(){
    const elements=new Map(),posts=[];
    const document={querySelector(selector){
        if(!elements.has(selector))elements.set(selector,{textContent:'',elements:{balance:{},reason:{},outcome:{},confirmation:{}},showModal(){this.open=true;},close(){this.open=false;},replaceChildren(){}});
        return elements.get(selector);
    },querySelectorAll(){return [{dataset:{action:'reset'}}];}};
    const context=vm.createContext({document,crypto:{randomUUID:()=> 'test-command'},clearInterval,setTimeout:callback=>callback(),
        fetch:async(url,request)=>{posts.push({url,body:JSON.parse(request.body)});return {ok:true,json:async()=>({})};}});
    vm.runInContext(source.slice(0,source.lastIndexOf('(async()=>')),context);
    return {context,e:selector=>document.querySelector(selector),posts};
}

test('euro displays use two decimals, preserve meaningful millieuro and input roundtrips',()=>{
    const {context}=dashboard();
    for(const [mills,display,input] of [[100,'0,10 €','0,10'],[20000,'20,00 €','20,00'],[3000,'3,00 €','3,00'],[1999910,'1.999,91 €','1999,91'],[154,'0,154 €','0,154'],[19684,'19,684 €','19,684'],[1999,'1,999 €','1,999'],[0,'0,00 €','0,00']]){
        assert.equal(context.money(mills),display);
        assert.equal(context.moneyInput(mills),input);
        assert.equal(context.milli(input),mills);
        assert.equal(context.milli(display.slice(0,-2)),mills);
    }
    assert.equal(context.money(-320),'-0,32 €');
    assert.equal(context.money(-2000000),'-2.000,00 €');
});

test('monetary parser accepts copied Italian and site English balances without guessing thousands',()=>{
    const {context}=dashboard();
    for(const [input,mills] of [['2000',2000000],['2000,00',2000000],['1,999.91',1999910],['1.999,91',1999910],['1.999.999,991',1999999991],['1,999,999.991',1999999991],['20.000',20000],['20,000',20000],[' 0,10 ',100]])assert.equal(context.milli(input),mills);
    for(const input of ['', '1,23.45','1.23,45','1.999.91','1,999,91','-1','1e3','1,0000','2000 €','NaN','9007199254740992'])assert.throws(()=>context.milli(input));
});

test('monetary inputs accept comma decimals and no loss is preselected',()=>{
    const html=fs.readFileSync(path.join(web,'index.html'),'utf8');
    for(const name of ['target','stake','balance'])assert.match(html,new RegExp('name="'+name+'" type="text" inputmode="decimal"'));
    assert.match(html,/<option value="" selected disabled>Scegli un esito verificato/);
    assert.match(html,/<option value="unknown">Esito non verificabile/);
    assert.doesNotMatch(html,/<option value="loss"[^>]*selected/);
});

test('balance verification clears the suggested amount and forces an explicit outcome',async()=>{
    const {context,e,posts}=dashboard();
    const device={id:'laptop',balance:19680,online:false,round:{id:'open'}};
    vm.runInContext('snapshot={devices:[]};refresh=async()=>{}',context);
    vm.runInContext('snapshot.devices=[{id:"laptop",balance:19680,online:false,round:{id:"open"}}]',context);
    await context.editBalance(device);
    const fields=e('#balance-form').elements;
    assert.equal(fields.balance.value,'');
    assert.equal(fields.outcome.value,'');
    assert.equal(fields.outcome.required,true);
    assert.match(e('#balance-instructions').textContent,/19,68 €/);
    fields.balance.value='1,999.91';fields.reason.value='Confronto con il credito sul sito';
    await e('#balance-form').onsubmit({preventDefault(){},currentTarget:{elements:fields}});
    assert.equal(posts.length,1,'only disarm was sent; blank outcome must not settle a round');
    fields.outcome.value='unknown';
    await e('#balance-form').onsubmit({preventDefault(){},currentTarget:{elements:fields}});
    assert.equal(posts[1].body.action,'reconcile');
    assert.equal(posts[1].body.payload.balance,1999910);
    assert.equal(posts[1].body.payload.outcome,'unknown');
});

test('clean restart is only submitted after the exact typed confirmation',async()=>{
    const {context,e,posts}=dashboard();
    let received;
    context.command=async(action,payload)=>{received={action,...payload};};
    const form=e('#reset-form');
    form.elements.confirmation.value='';
    await form.onsubmit({preventDefault(){},currentTarget:form});
    assert.equal(received,undefined);
    form.elements.confirmation.value='RIPARTI';
    await form.onsubmit({preventDefault(){},currentTarget:form});
    assert.deepEqual(received,{action:'reset',confirmation:'RIPARTI'});
    assert.equal(posts.length,0,'tests never reset a running master');
});

test('quiescence waits for disarm and emergency acknowledgements, including legacy zero defaults',()=>{
    const {context}=dashboard();
    assert.equal(context.quiescent({online:true,ready:false,busy:false}),true);
    assert.equal(context.quiescent({online:true,ready:false,busy:false,disarm:1,disarm_ack:0}),false);
    assert.equal(context.quiescent({online:true,ready:false,busy:false,disarm:1,disarm_ack:1,emergency:2,emergency_ack:1}),false);
    assert.equal(context.quiescent({online:true,ready:false,busy:false,disarm:1,disarm_ack:1,emergency:2,emergency_ack:2}),true);
    assert.equal(context.quiescent({online:true,ready:false,busy:true}),false);
});

test('balance dialog does not open before the laptop acknowledges disarm',async()=>{
    const {context,e,posts}=dashboard();
    vm.runInContext('snapshot={devices:[{id:"laptop",online:true,ready:false,busy:false,disarm:1,disarm_ack:0,balance:19680}]};let polls=0;refresh=async()=>{if(++polls===3)snapshot.devices[0].disarm_ack=1;}',context);
    await context.editBalance({id:'laptop'});
    assert.equal(vm.runInContext('polls',context),3);
    assert.equal(e('#balance-editor').open,true);
    assert.equal(posts.length,1);
    assert.equal(posts[0].body.action,'disarm');
});

test('confirmed reset disarms online associated laptops and waits for acknowledgements first',async()=>{
    const {context,posts}=dashboard();
    vm.runInContext('snapshot={devices:[{id:"laptop",associated:true,online:true,ready:false,busy:false,disarm:1,disarm_ack:0},{id:"offline",associated:true,online:false},{id:"archived",associated:false,online:true}]};let polls=0;refresh=async()=>{if(++polls===3)snapshot.devices[0].disarm_ack=1;}',context);
    await context.command('reset',{confirmation:'RIPARTI'});
    assert.equal(posts.length,2);
    assert.equal(posts[0].body.action,'disarm');
    assert.equal(posts[0].body.payload.id,'laptop');
    assert.equal(posts[1].body.action,'reset');
    assert.equal(vm.runInContext('polls',context),4);
});

test('reset remains pending when a disarm acknowledgement is missing and sends no reset',async()=>{
    const {context,e,posts}=dashboard();
    vm.runInContext('snapshot={devices:[{id:"laptop",online:true,ready:false,busy:false,disarm:1,disarm_ack:0}]};refresh=async()=>{};',context);
    await context.command('reset',{confirmation:'RIPARTI'});
    assert.equal(posts.length,1);
    assert.equal(posts[0].body.action,'disarm');
    assert.match(e('#error').textContent,/conferma del laptop/);
    await context.command('reset',{confirmation:'NO'});
    assert.equal(posts.length,1,'a missing typed confirmation must never disarm a laptop');
});

test('activity durations show hours and minutes, including more than one day',()=>{
    const {context}=dashboard();
    assert.equal(context.duration(2700),'0 h 45 min');
    assert.equal(context.duration(18000),'5 h 00 min');
    assert.equal(context.duration(86400),'24 h 00 min');
    assert.equal(context.duration(90060),'25 h 01 min');
    assert.equal(context.duration(0),'0 h 00 min');
    assert.equal(context.duration(1),'0 h 00 min 1 s');
    assert.equal(context.duration(2700.9),'0 h 45 min');
});

test('budget duration fields preserve exact seconds across load and save',async()=>{
    const {context,e,posts}=dashboard();
    for(const budget of [1,59,60,2701,18000,86399,86400]){
        const [hours,minutes,seconds]=context.durationInput(budget);
        assert.equal(context.budgetSeconds({hours:{value:String(hours)},minutes:{value:String(minutes)},seconds:{value:String(seconds)}}),budget);
    }
    vm.runInContext('refresh=async()=>{}',context);
    const fields={target:{value:'3,00'},hours:{value:'0'},minutes:{value:'0'},seconds:{value:'1'},minimum:{value:'1'},max_sessions:{value:'0'},automatic:{checked:false}};
    await e('#limits').onsubmit({preventDefault(){},currentTarget:{elements:fields}});
    assert.equal(posts[0].body.action,'settings');
    assert.equal(posts[0].body.payload.budget,1,'an existing one-second budget must not become zero');
    fields.hours.value='5';fields.minutes.value='45';fields.seconds.value='3';
    await e('#limits').onsubmit({preventDefault(){},currentTarget:{elements:fields}});
    assert.equal(posts[1].body.payload.budget,20703);
    const html=fs.readFileSync(path.join(web,'index.html'),'utf8');
    for(const name of ['hours','minutes','seconds'])assert.match(html,new RegExp('name="'+name+'" type="number"[^>]*step="1"'));
});

test('budget form rejects fractions and out-of-range duration components',()=>{
    const {context}=dashboard();
    for(const [hours,minutes,seconds] of [['0','0','0'],['0.75','0','0'],['0','60','0'],['0','0','60'],['24','0','1'],['25','0','0'],['','0','1'],['-1','0','0']]){
        assert.throws(()=>context.budgetSeconds({hours:{value:hours},minutes:{value:minutes},seconds:{value:seconds}}));
    }
});
