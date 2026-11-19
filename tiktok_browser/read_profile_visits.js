// Run via tab.playwright.evaluate(readProfileVisits) on the signed-in TikTok
// Activity > All activity page. This reader never guesses a visitor's identity.
function readProfileVisits() {
  const inbox = document.getElementById("header-inbox-list");
  if (!inbox) return { status: "inbox_unavailable", visits: [] };

  // Only match a single visitor. Grouped notifications do not establish
  // which profile link belongs to which person.
  const visitText = /^(?:(?:has )?(?:viewed|visited) your profile|(?:wyświetlił(?:a)?|odwiedził(?:a)?) twój profil)$/iu;
  const profiles = new Set();
  for (const row of inbox.querySelectorAll("li, [role='listitem']")) {
    if (row.querySelector("li, [role='listitem']")) continue;
    const accounts = new Set();
    for (const link of row.querySelectorAll("a[href]")) {
      const url = new URL(link.href, document.baseURI);
      const profile = /^\/@([a-z0-9._]{2,24})\/?$/i.exec(url.pathname);
      if (url.origin === location.origin && profile) accounts.add(profile[1].toLowerCase());
    }
    if (accounts.size !== 1) continue;
    const message = row.cloneNode(true);
    for (const node of message.querySelectorAll("a, time, button, svg, [aria-hidden='true']")) node.remove();
    const text = message.textContent.replace(/\s+/g, " ").trim()
      .split(/\s*[·•]\s*/u)[0].replace(/[.!]$/u, "").trim();
    if (visitText.test(text)) profiles.add([...accounts][0]);
  }
  return { status: profiles.size ? "named_visits" : "no_named_visits_seen", visits: [...profiles] };
}
