'use strict';
const crypto = require('node:crypto');

// A transport failure marker is not a Google AI answer. Only a verified
// reply to the exact issue body can stop the separate cold review.
function hasAuthenticatedGoogleAnswer(comments, issue) {
  const consult = issue.title.startsWith('[consult]');
  const digest = crypto.createHash('sha256').update(issue.body || '', 'utf8').digest('hex');
  return comments.some(c => {
    if (c.user?.login !== 'github-actions[bot]') return false;
    const body = c.body || '';
    if (consult) {
      if (!body.startsWith('Konsultant/2 ')) return false;
      try {
        const result = JSON.parse(body.slice('Konsultant/2 '.length));
        return result.issue === issue.number && result.sha256 === digest &&
          Number(result.google_ai_responses_received) > 0 &&
          (result.review === 'SPRAWDZONE' || result.review === 'DO POPRAWY');
      } catch (_) {
        return false;
      }
    }
    return body.startsWith('Google AI: SPRAWDZONE') ||
           body.startsWith('Google AI: DO POPRAWY') ||
           (body.startsWith('Google AI Mode answer') &&
            /AI RESPONSE READY: (True|true)/.test(body));
  });
}

// Report actual received Google feedback rather than claiming that no reply
// arrived merely because Google found insufficient evidence.
function describeUnresolvedReceipt(receipt) {
  const answers = Number(receipt?.google_ai_responses_received || 0);
  if (!receipt || !Number.isFinite(answers) || answers <= 0) {
    return String(receipt?.reason ||
      'No authenticated Google AI receipt after the available retries.');
  }
  if (typeof receipt.reason === 'string' && receipt.reason.trim()) {
    return receipt.reason.trim();
  }
  const blocked = Array.isArray(receipt.blocked)
    ? receipt.blocked.filter(s => typeof s === 'string' && s.trim())
    : [];
  return blocked.length
    ? 'Google AI responded, but requirements remain unverified: ' +
      blocked.join('; ')
    : 'Google AI responded, but the solution remains unconfirmed.';
}

module.exports = { hasAuthenticatedGoogleAnswer, describeUnresolvedReceipt };
