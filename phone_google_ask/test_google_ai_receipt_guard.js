'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const crypto = require('node:crypto');
const {hasAuthenticatedGoogleAnswer: ok} = require('./google_ai_receipt_guard.js');
const issue = { number: 288, title: '[consult] sample', body: '{"question":"test"}' };
const sha256 = crypto.createHash('sha256').update(issue.body).digest('hex');
const comment = (data, user='github-actions[bot]') => ({user:{login:user},body:'Konsultant/2 '+JSON.stringify(data)});
const approved = { issue:288,sha256,review:'SPRAWDZONE',status:'POTWIERDZONE',google_ai_responses_received:2 };

test('transport failure is not an AI answer', () => {
  assert.equal(ok([comment({issue:288,sha256,review:'NIEPOTWIERDZONE',status:'NIEPOTWIERDZONE'})],issue),false);
});
test('zero responses do not suppress cold fallback', () => {
  assert.equal(ok([comment({...approved,google_ai_responses_received:0})],issue),false);
});
test('genuine verified Google verdict stops fallback', () => {
  assert.equal(ok([comment(approved)],issue),true);
});
test('DO POPRAWY is a real Google verdict', () => {
  assert.equal(ok([comment({...approved,review:'DO POPRAWY',status:'NIEPOTWIERDZONE'})],issue),true);
});
test('different issue, wrong hash and wrong sender are rejected', () => {
  assert.equal(ok([comment({...approved,issue:287})],issue),false);
  assert.equal(ok([comment({...approved,sha256:'x'})],issue),false);
  assert.equal(ok([comment(approved,'attacker')],issue),false);
});
test('malformed or unrecognized verdicts are rejected', () => {
  assert.equal(ok([{user:{login:'github-actions[bot]'},body:'Konsultant/2 invalid'}],issue),false);
  assert.equal(ok([comment({...approved,review:'NIEPOTWIERDZONE'})],issue),false);
});
test('ordinary Google ask still works', () => {
  const generic={number:5,title:'[google-ask] review',body:'question'};
  assert.equal(ok([{user:{login:'github-actions[bot]'},body:'Google AI: DO POPRAWY'}],generic),true);
  assert.equal(ok([{user:{login:'github-actions[bot]'},body:'Google AI: NIEPOTWIERDZONE'}],generic),false);
});
