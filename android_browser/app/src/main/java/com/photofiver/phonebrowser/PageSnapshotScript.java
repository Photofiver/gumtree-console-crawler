package com.photofiver.phonebrowser;

/** Extract public pages and real result links, excluding Google menu/navigation links. */
final class PageSnapshotScript {
    private PageSnapshotScript() {}

    static String javascript() {
        return """
            (() => {
              const google = /(^|\\.)google\\.[a-z.]+$/i.test(location.hostname);
              const anchors = [...document.querySelectorAll('a[href],a[data-url],a[data-href]')];
              function destination(a) {
                const candidates = [a.getAttribute('data-url'), a.getAttribute('data-href'),
                    a.getAttribute('href'), a.href].filter(Boolean);
                for (const candidate of candidates) {
                  try {
                    let u = new URL(candidate, location.href);
                    for (let pass = 0; pass < 2; pass++) {
                      if (!/(^|\\.)google\\.[a-z.]+$/i.test(u.hostname)
                          || !/^\\/(url|aclk|imgres)$/.test(u.pathname)) break;
                      const target = u.searchParams.get('url') || u.searchParams.get('q')
                          || u.searchParams.get('adurl') || u.searchParams.get('imgurl');
                      if (!target) break;
                      u = new URL(target, location.href);
                    }
                    if (u.protocol === 'https:' && !u.username && !u.password)
                      return u.href;
                  } catch (e) {}
                }
                return '';
              }
              const entries = [];
              const used = new Set();
              for (const a of anchors) {
                const heading = a.querySelector('h3,[role=heading]');
                const rawText = (a.innerText || a.getAttribute('aria-label') || '').trim();
                // Google's result cards have a heading or an explicit displayed website.
                // Avoid mistaking its History, Lens and other UI links for search results.
                const displayedSite = /(?:https?:\\/\\/|www\\.)[a-z0-9.-]+\\.[a-z]{2,}/i.test(rawText);
                if (google && !heading && !displayedSite) continue;
                const url = destination(a);
                if (!url || used.has(url)) continue;
                const u = new URL(url);
                const isRedirect = google && /(^|\\.)google\\.[a-z.]+$/i.test(u.hostname)
                    && /^\\/(goto|url)$/.test(u.pathname);
                if (google && /(^|\\.)google\\.[a-z.]+$/i.test(u.hostname) && !isRedirect)
                  continue;
                const title = ((heading && heading.innerText) || rawText).trim().slice(0,160);
                if (!title) continue;
                used.add(url);
                entries.push({text:title, url, type:isRedirect?'google-redirect':'direct',
                    verifiedResult:!!heading});
              }
              // The first entries correspond to result titles, not global site navigation.
              entries.sort((a,b) => Number(b.verifiedResult)-Number(a.verifiedResult));
              const links = entries.slice(0,50);
              const diagnostics = [];
              if (google && entries.length < 2) {
                for (const a of anchors.slice(0,30)) {
                  diagnostics.push({text:(a.innerText||'').trim().slice(0,100),
                    href:(a.getAttribute('href')||'').slice(0,300),
                    hasHeading:!!a.querySelector('h3,[role=heading]')});
                }
              }
              return JSON.stringify({
                title:document.title, url:location.href,
                text:(document.body?document.body.innerText:'').slice(0,6500),
                links, totalResultLinks:entries.length, resultLinksLimited:entries.length>50,
                anchorCount:anchors.length,
                resultHeadingCount:document.querySelectorAll('h3,[role=heading]').length,
                linkDiagnostics:diagnostics
              });
            })()
            """;
    }
}
