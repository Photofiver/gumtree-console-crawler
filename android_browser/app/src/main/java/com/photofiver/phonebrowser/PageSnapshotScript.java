package com.photofiver.phonebrowser;

/** Read public page content and normalize search-result redirect links. */
final class PageSnapshotScript {
    private PageSnapshotScript() {}

    static String javascript() {
        return """
            (() => {
              const google = /(^|\\.)google\\.[a-z.]+$/i.test(location.hostname);
              const anchors = Array.from(document.querySelectorAll('a[href],a[data-url],a[data-href]'));
              function destination(a) {
                const candidates = [a.getAttribute('data-url'), a.getAttribute('data-href'),
                    a.getAttribute('href'), a.href].filter(Boolean);
                for (let candidate of candidates) {
                  try {
                    let u = new URL(candidate, location.href);
                    // Google sometimes uses /url?q=<destination> instead of a direct outbound href.
                    for (let pass = 0; pass < 2; pass++) {
                      if (!/(^|\\.)google\\.[a-z.]+$/i.test(u.hostname)
                          || !/^\\/(url|aclk|imgres)$/.test(u.pathname)) break;
                      const to = u.searchParams.get('url') || u.searchParams.get('q')
                          || u.searchParams.get('adurl') || u.searchParams.get('imgurl');
                      if (!to) break;
                      u = new URL(to, location.href);
                    }
                    if (u.protocol === 'https:' && u.username === '' && u.password === '') {
                      return u.href;
                    }
                  } catch (e) {}
                }
                return '';
              }
              const titled = anchors.filter(a => a.querySelector('h3'));
              const ordered = [...titled, ...anchors];
              const found = [];
              const used = new Set();
              for (const a of ordered) {
                const url = destination(a);
                const heading = a.querySelector('h3');
                const title = ((heading && heading.innerText) || a.innerText
                    || a.getAttribute('aria-label') || '').trim().slice(0,110);
                if (!url || !title || used.has(url)) continue;
                const dest = new URL(url);
                if (google && /(^|\\.)google\\.[a-z.]+$/i.test(dest.hostname)
                    && !heading) continue; // Ignore internal Google navigation.
                used.add(url);
                found.push({text:title, url:url.slice(0,450)});
                if (found.length >= 25) break;
              }
              const diagnostics = [];
              if (google && found.length < 2) {
                for (const a of [...titled, ...anchors].slice(0,22)) {
                  diagnostics.push({text:(a.innerText||'').trim().slice(0,80),
                    href:(a.getAttribute('href')||'').slice(0,280),
                    dataUrl:(a.getAttribute('data-url')||'').slice(0,280),
                    hasHeading:!!a.querySelector('h3')});
                }
              }
              return JSON.stringify({
                title:document.title, url:location.href,
                text:(document.body ? document.body.innerText : '').slice(0,6500),
                links:found, linkDiagnostics:diagnostics
              });
            })()
            """;
    }
}
