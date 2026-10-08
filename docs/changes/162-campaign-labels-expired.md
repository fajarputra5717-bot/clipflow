# 162 · P3 part 6: campaign-driven clip labels + collapsed "Expired" group (Review, Publish); digest skips expired · campaign_status, main.py, routes_editor, review.js, index.html, digest

- **Why:** P3 spec part 6 + roadmap "P3 · Campaign step spec" item 3 (owner 2026-10-07).
- **One rule:** `campaign_status.clip_labels(rules, posts, now)` → `{earn, expired}`. expired = the campaign's
  status is Ended (158: past the last posting day; IME after 28 Oct); then earn = "Campaign ended". Otherwise
  earn = Lane B's `review_state.earn_state` ("Week closed": every post went up in a closed week, or unposted
  and outside every window), else None. "Not eligible: <reason>" stays the post-level flag (131/132) and claim
  advice "Missed" + reason (133).
- **Review (routes_editor `review/clips` + review.js):** clips carry `earn` + `expired`; expired ones leave the
  grid for a collapsed `<details class="rv-expired">` "Expired · N clips (campaign ended)" (open state kept
  across refreshes); earn badge and sort-last unchanged.
- **Editor:** `GET …/editor` returns `campaign_labels` (same rule); the Editor page header shows it in Lane B's
  next editor commit (editor.js is mid-rework there).
- **Publish:** cards carry `earn` (badge next to the summary) + `expired`; groups of ended campaigns render in one
  collapsed "Expired · N clips (campaign ended)" group at the bottom, outside the filters' active list.
- **Digest (142):** "Ready to post" skips clips of ended campaigns. Nothing is deleted anywhere.
- **Lane C Low (160, qa 6580bc4):** Get another hook also removes `audio.silence_trim` (its ranges were the old
  moment's), so the switch isn't left on with nothing removed.

**Verified:** unit OK (`test_campaign_status` +clip_labels: W1 post on 9 Oct "Week closed", 30 Oct "Campaign
ended" + expired, no rules → none); UI 161 passed (Publish earn chip + Expired group; Review Expired group);
prod: 6/6 up, publish queue + review clips (48) read-only OK, none expired today; digest preview OK.
