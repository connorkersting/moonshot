# Publishing checklist (nothing here has been run)

This repo is local only: no remote. Run these yourself if and when you decide to publish. Last
refreshed from the `v28-final` tag of the pipeline repo.

## Before anything goes public

1. **Music.** The old Holst caveat is closed. Versions v2 to v12 used Holst's "Mars" in a US Air
   Force Band recording whose 1998 wind-band transcription had an unconfirmed status. v13
   replaced it with Beethoven's Egmont overture (Czech National Symphony Orchestra, released by
   Musopen, public domain worldwide), and v28 uses only Musopen recordings: Dvořák's finale and
   Largo plus the Egmont. Publish v13 or later only; v2 to v12 stay private. One loose end
   remains: CREDITS.md names the Egmont performers but the two Dvořák rows say only "Musopen".
   Check the performers on their Commons pages before quoting them in a post.
2. **Watch the final cut once with sound.** The AI critics never heard it. The director's ear is
   the only audio check that counts, and he made the audio calls on 0:33, 1:02 and the v24
   staging sound. The final Fable review of v28 could not hear it either (its sound score of 8 is
   from structure).
3. **Re-run the scrub scan** after any edit:
   `git grep -n -i -E "conno[^r]|users[\\/]|appdata|@gmail|api[_-]?key|sk-|\.env"`. Review every
   hit; the expected ones are the `.env.example` file, the `.gitignore` entry and the docs that
   describe them. "Connor Kersting" is the director's public credit (it is on screen in the
   video) and appears in the credits-card code and in comments; that is intended.
4. **NASA media guidelines.** No NASA insignia is used; keep "Not affiliated with or endorsed by
   NASA" in the video credits and the README.
5. **Sonniss files** must never be committed. The licence forbids redistributing the files and
   forbids AI/ML training. `.gitignore` blocks audio formats; check `git status` before every
   push. The released MP4 has Sonniss effects mixed into its sound; read the licence once more
   before you attach it to a release. Do not upload a mix containing them to any service that
   may train on uploads.
6. **Large assets are not in this repo.** The pre-rendered Blender frames, the 10K scans, the
   RIFE slow-mo clip and the v24 audio master are listed with their sizes in
   `pipeline/ASSETS.md`, with the manifests that pin their hashes in `pipeline/asset_manifests/`.
7. **Local-only folders.** `analytics/.env`, `analytics/.tmp/`, `analytics/.venv/`, the DuckDB
   file and the study packs are git-ignored. Don't copy the `analytics/` folder by hand; clone.
8. **Your own words.** The README's "Who decided what" section is drawn from the run log. A
   short first-person paragraph about your role, in your voice, belongs next to it before
   you post anything. Nothing in this refresh was written as you.
9. **No CI yet.** A workflow that runs `dbt build` on the committed CSVs
   (`analytics/data/raw/`) and `py_compile` over `pipeline/` would be a small first addition.

## Create the GitHub repo and push

The refresh lives on the branch `refresh-v28`, on top of the first export commit. Open a pull
request from it, even on your own repo, and merge that, so the history reads as a project.

```bash
gh repo create moonshot --public --source . --remote origin --description "An overnight Claude Code agent loop that cut an Apollo 11 trailer from NASA public-domain footage"
git push -u origin main
git push -u origin refresh-v28
gh pr create --base main --head refresh-v28 --title "Refresh to v28: final pipeline, docs and analytics" --body "What changed and why: see MAKING-OF.md."
gh repo edit --add-topic claude-code --add-topic mcp --add-topic ai-agents --add-topic video-editing --add-topic blender --add-topic ffmpeg --add-topic apollo-11 --add-topic dbt --add-topic duckdb
```

## Release with the video

`MOONSHOT_RAW_vs_FINAL.mp4` in the exports folder was built from v12 and has not been rebuilt for
v28; rebuild it (`pipeline/raw_conform.py 28`) or leave it out of the release.

```bash
gh release create v2.0 MOONSHOT_FINAL.mp4 --title "MOONSHOT v28" --notes "Final trailer (87.5 s, 1080p24, -13.8 LUFS). Media: NASA public domain; music: public-domain Musopen recordings; not affiliated with or endorsed by NASA."
```

The MP4 is under GitHub's 2 GB release-asset limit; check the size first.

## Pin

Pin the repo from your GitHub profile page (Customize your pins). The `gh` CLI has no pin command.
