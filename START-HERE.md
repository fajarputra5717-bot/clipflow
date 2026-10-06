# ClipFlow rebuild — start here

The old disk is gone, so this kit replaces **Phase 0, 2 and 5** of
`MIGRATION-RUNBOOK.md`. The other phases still apply:

| Runbook phase | Do it? |
|---|---|
| 0 Protect old disk / 2 Recover .vmdk / 5 Restore | **Skip** |
| 1 Install Proxmox + SATA SSD storage | Yes |
| 3 Create the Ubuntu VM | Yes |
| 4 Ubuntu prep, `/data` mount, Docker, log caps | Yes |
| 6 Verify / 7 Git + backups | Replaced by steps 3–6 below |

---

## 1. Copy the kit to the VM (from your laptop)

```bash
scp clipflow-rebuild.tar.gz clipflow@<VM_IP>:~
ssh clipflow@<VM_IP>
```

## 2. Install and start (on the VM)

```bash
tar xzf clipflow-rebuild.tar.gz
sudo bash riftstorm/scripts/bootstrap.sh
```

It installs to `/opt/clipflow`, generates the DB password and the first
admin's password (`CLIPFLOW_ADMIN_USER` / `CLIPFLOW_ADMIN_PASSWORD` in `.env`), prepares `/data`, makes the first git commit, builds the
images (the first build takes 10–20 min: torch + whisper) and starts everything.
It ends by printing `{"status":"healthy"}` and the URL.

Then add your keys and restart:

```bash
nano /opt/clipflow/.env        # GEMINI_API_KEY, ANTHROPIC_API_KEY, SUBMAGIC_API_KEY, RUNWAY, YOUTUBE_*, TELEGRAM_*
cd /opt/clipflow && docker compose up -d
```

## 3. Things that were lost and must be redone by hand

- API keys (above). Save a copy of `.env` in your password manager **today**.
- The watermark PNG: re-upload it under Settings → Watermark · asset library.
- Old jobs/clips: gone. Finished clips you already posted are still on YouTube/TikTok.
- n8n workflows: if you used them, start n8n with `docker compose --profile n8n up -d`
  and rebuild them at `http://<VM_IP>:5678`.
- telegram-monitor: its code wasn't in any surviving copy. Tell Claude what it did
  and it can be rebuilt as a small service later.

## 4. Push to a private GitHub repo (so this never happens again)

Create an **empty private** repo on github.com (no README), then:

```bash
cd /opt/clipflow
git ls-files | grep -x .env && echo "STOP: .env is tracked" || echo "ok: .env not tracked"
ssh-keygen -t ed25519 -C clipflow-vm -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub     # add at GitHub → repo → Settings → Deploy keys (allow write)
git remote add origin git@github.com:<YOUR_USER>/clipflow.git
git push -u origin main
```

## 5. Nightly database backup

```bash
echo "30 2 * * * root /opt/clipflow/scripts/backup-db.sh" | sudo tee /etc/cron.d/clipflow-backup
sudo /opt/clipflow/scripts/backup-db.sh && ls -lh /data/backups
```

Plus runbook Phase 7's Proxmox backup of the VM (system disk only).

## 6. Install Claude Code and give it the repo

```bash
curl -fsSL https://claude.ai/install.sh | bash
cd /opt/clipflow && claude
```

Running `claude` inside `/opt/clipflow` gives it the whole codebase. The
`clipflow` user owns the folder and is in the `docker` group, so it can build,
restart and read logs. (Log out and back in once after bootstrap so the
group change applies.)

---

## Prompts for Claude Code (paste one per session)

**Session 1**
```
Read REBUILD.md, then CLAUDE.md. We're rebuilding ClipFlow on a fresh server
after losing the old one. Do R-01 to R-03 in order, following REBUILD.md's ground rules
(one commit per task, docs/changes entry + INDEX line, verify on the running stack).
Never print or commit .env. After each task, git push. Stop after R-03 and
report in under 10 lines per task: what changed, how you verified, what you did NOT verify.
```

**Session 2**: `Continue REBUILD.md: R-04 to R-11. Same rules. Stop after R-11 and report.`

**Session 3**: `Continue REBUILD.md: R-12 to R-13. Same rules. Install Playwright + Chromium on this VM if possible and use it to verify clicks and motion; if not possible, say so. Stop and report.`

**Session 4**: `Continue REBUILD.md: R-14, R-16, R-17. Same rules. Render real clips at 60:40 and 70:30 and inspect frames. Stop and report.`

**Session 5**: `Continue REBUILD.md: R-18 to R-22. Same rules. R-20 must be its own commit with no behaviour change. Stop and report.`

**Session 6**: `List R-15, R-23 and R-24 from REBUILD.md and ask me which ones to rebuild. Don't build anything yet.`

After that, the TODO list at the bottom of REBUILD.md is the normal roadmap again.
