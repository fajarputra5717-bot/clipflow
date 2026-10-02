# 115 · Campaign clips get their description at analysis (hashtag chip starts green) · worker.py, main.py, shared/descriptions.py, shared/campaigns.py

**Before.** Analysis never wrote a description; only "Generate description" did. So every new campaign clip
started at "Fix 1 rule to approve" (109's hashtag chip red).

**Now.**
- `shared/descriptions.py`: the description prompt + schema, moved verbatim out of main.py's "Generate
  description" endpoint (byte-identical prompt checked for campaign / non-campaign, id / en). The endpoint uses it.
- `shared/campaigns.with_campaign_hashtags()` (moved from main.py; main.py keeps a thin wrapper).
- Worker `campaign_description()`: after a campaign clip's preview, if its description is EMPTY, one utility-model
  call (task `description`, the clip's language) writes it and the campaign hashtags are appended in exact order.
  Never overwrites an existing description (also guarded in SQL); never fails the render. "Generate description"
  stays for regenerating.

**Verified:** Windah clip 1ec2b078 (empty description) re-rendered → "Dikejar setan merah terus menerus?! … ada
harapan fire exit!" + "#windahbasudara #windahMKLIP2 #motionklip #ezklip" (Claude, Indonesian); its hashtag chip
is green; the untouched sibling still red until its next render.
