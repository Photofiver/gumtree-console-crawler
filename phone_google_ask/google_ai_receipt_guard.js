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
module.exports = { hasAuthenticatedGoogleAnswer };
