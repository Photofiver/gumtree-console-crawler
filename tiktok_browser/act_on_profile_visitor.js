// Work browser action for one visitor identified by an actual TikTok profile link.
// The caller supplies locators grounded in the live UI, scoped to this profile
// and chat. Missing controls are normal and must not be replaced with guesses.
// ledger.claim(handle, action) must persist intent once, before a click. It must
// return false for existing intents or outcomes, including ambiguous attempts.
// ledger.finish persists the outcome. Neither operation may use public storage.
async function actOnProfileVisitor({ tab, profileUrl, profile, conversation, ledger }) {
  const url = new URL(profileUrl);
  const match = /^\/@([a-z0-9._]{2,24})\/?$/i.exec(url.pathname);
  if (url.origin !== "https://www.tiktok.com" || !match) throw Error("Invalid visitor link");
  const handle = match[1].toLowerCase();
  if (handle === "photofiver.photof") throw Error("Self profile");
  const message = "Thanks for visiting! Follow @photofiver.photof for more cat videos 🐱";
  function sameProfile(href) {
    if (!href) return false;
    const actual = new URL(href, url);
    return actual.origin === url.origin &&
      actual.pathname.replace(/\/$/, "").toLowerCase() === "/@" + handle;
  }
  async function visible(control) {
    return Boolean(control && await control.count() === 1 && await control.isVisible());
  }
  async function perform(action, click, confirm) {
    if (!await ledger.claim(handle, action)) return "previously_recorded";
    let result = "unknown";
    try {
      await click();
      result = await confirm();
    } finally {
      await ledger.finish(handle, action, result);
    }
    return result;
  }
  if (!sameProfile(await tab.url())) throw Error("Visitor profile mismatch");
  let follow = "unavailable";
  if (await visible(profile.following)) follow = "already_following";
  else if (await visible(profile.requested)) follow = "pending";
  else if (await visible(profile.follow)) {
    follow = await perform("follow", () => profile.follow.click(), async () => {
      await profile.following.or(profile.requested).waitFor({state:"visible",timeoutMs:5000});
      return await visible(profile.following) ? "followed" : "pending";
    });
  }
  if (!await visible(profile.message)) return { follow, invite: "unavailable" };
  await profile.message.click();
  const chat = await conversation();
  if (!chat || !await visible(chat.recipientLink) ||
      !sameProfile(await chat.recipientLink.getAttribute("href"))) {
    return { follow, invite: "recipient_unverified" };
  }
  // An existing thread can contain an earlier/manual invitation. Skip unless
  // TikTok positively identifies a new chat or first message request.
  if (!await visible(chat.newConversation) || !await visible(chat.composer)) {
    return { follow, invite: "not_a_new_conversation" };
  }
  const bubble = chat.outgoingMessage(message);
  if (await bubble.count()) return { follow, invite: "already_present" };
  const invite = await perform("invite", async () => {
    await chat.composer.fill(message);
    if (!await visible(chat.send)) throw Error("Send control unavailable");
    await chat.send.click();
  }, async () => {
    await bubble.waitFor({state:"visible",timeoutMs:5000});
    // Receipt must be an explicit sent/request-sent indicator for this send.
    await chat.sentReceipt.waitFor({state:"visible",timeoutMs:5000});
    return "sent";
  });
  return { follow, invite };
}
