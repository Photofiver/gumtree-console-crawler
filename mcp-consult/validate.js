import {createHash} from 'node:crypto';
export function validateReceipt(issue,comments){
 const digest=createHash('sha256').update(issue.body||'','utf8').digest('hex');
 const matches=comments.filter(c=>c.user?.login==='github-actions[bot]'&&c.body?.startsWith('Konsultant/2 ')).flatMap(c=>{
  try{const x=JSON.parse(c.body.slice(13));return x.issue===issue.number&&x.sha256===digest?[{id:c.id,receipt:x}]:[];}catch{return [];}
 });
 const latest=matches.at(-1);
 if(!latest)return {valid:false,reason:'No matching authenticated receipt'};
 const r=latest.receipt;
 return {valid:true,comment_id:latest.id,status:r.status||'UNKNOWN',review:r.review||'UNKNOWN',responses:Number(r.google_ai_responses_received||0),approved:r.status==='POTWIERDZONE'&&r.review==='SPRAWDZONE'&&Number(r.google_ai_responses_received)>0};
}
