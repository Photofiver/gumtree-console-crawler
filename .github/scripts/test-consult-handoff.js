const fs = require('node:fs');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {AsyncFunction} = Object.getPrototypeOf(async function(){}).constructor;
const yaml = fs.readFileSync('.github/workflows/consult-no-api-handoff.yml','utf8');
const match = yaml.match(/          script: \|\n([\s\S]*?)\n(?=\S|$)/);
assert.ok(match, 'GitHub script found');
const script = match[1].split('\n').map(line => line.replace(/^            /, '')).join('\n');
const fn = new AsyncFunction('require','context','github','core','process',script);
async function test({receipt,comments=[],expectedPosts=1,expectedFailed=false}) {
  const body = 'test question';
  const issue = {title:'[consult] test',body};
  const sha256 = crypto.createHash('sha256').update(body).digest('hex');
  const base = {issue:293,sha256,status:'DO POPRAWY',review:'DO POPRAWY',google_ai_responses_received:1};
  const record = {id:42,user:{login:'github-actions[bot]'},body:'Konsultant/2 '+JSON.stringify({...base,...receipt})};
  const posts = [];
  let failure;
  const github = {
    rest:{issues:{
      get:async()=>({data:issue}),
      listComments:async()=>({data:[record,...comments]}),
      createComment:async({body})=>{posts.push(body);}
    }},
    paginate:async()=>[record,...comments]
  };
  const summary = {addHeading(){return this},addRaw(){return this},write(){return Promise.resolve()}};
  await fn(require,{repo:{owner:'Photofiver',repo:'gumtree-console-crawler'}},github,{setFailed:m=>failure=m,info(){},summary},{env:{ISSUE_NUMBER:'293'}});
  assert.equal(posts.length,expectedPosts);
  assert.equal(Boolean(failure),expectedFailed);
  return posts;
}
(async()=>{
  const [p] = await test({});
  assert.match(p,/requires revision/);
  const [approved] = await test({receipt:{status:'POTWIERDZONE',review:'SPRAWDZONE'}});
  assert.match(approved,/verified/);
  await test({comments:[{id:43,user:{login:'github-actions[bot]'},body:'<!-- consultation-handoff:42 -->'}],expectedPosts:0});
  await test({receipt:{sha256:'incorrect'},expectedPosts:0,expectedFailed:true});
  await test({receipt:{issue:999},expectedPosts:0,expectedFailed:true});
  console.log('PASS: revision, approval, deduplication, wrong SHA, wrong issue');
})().catch(e=>{console.error(e);process.exitCode=1});
