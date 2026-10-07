# Publishing checklist (nothing here has been run)

This repo is local only: one commit, no remote. Run these yourself if and when you decide to
publish.

## Before anything goes public

1. **Holst "Mars."** The recording is public domain (US Air Force Band), but it plays a 1998
   wind-band transcription by Merlin Patterson whose copyright status is unconfirmed. Either swap
   it for a public-domain orchestral recording of the original score and re-render, or confirm the
   arrangement's status. See CREDITS.md.
2. **Watch the final cut once with sound.** The critics never heard it; they read loudness and
   intelligibility measurements.
3. **Re-run the scrub scan** after any edit:
   `git grep -n -i -E "users[\\/]|appdata|@gmail|api[_-]?key|token|password"` should print nothing.
4. **NASA media guidelines.** No NASA insignia is used; keep "Not affiliated with or endorsed by
   NASA" in the video credits and README.
5. **Sonniss files** must never be committed (the licence forbids redistribution). `.gitignore`
   blocks audio formats; check `git status` before every push.

## Create the GitHub repo and push

```bash
gh repo create moonshot --public --source . --remote origin --description "An overnight Claude Code agent loop that cut an Apollo 11 trailer from NASA public-domain footage"
git push -u origin main
gh repo edit --add-topic claude-code --add-topic mcp --add-topic ai-agents --add-topic video-editing --add-topic blender --add-topic ffmpeg --add-topic apollo-11 --add-topic generative-workflows
```

## Release with the two videos

```bash
gh release create v1.0 MOONSHOT_FINAL.mp4 MOONSHOT_RAW_vs_FINAL.mp4 --title "MOONSHOT v1.0" --notes "Final trailer (81.8 s, 1080p24, -13.8 LUFS) and the raw-vs-final side-by-side. Media: NASA public domain; music: public-domain recordings; not affiliated with or endorsed by NASA."
```

Each MP4 is under GitHub's 2 GB release-asset limit; check the sizes first.

## Pin

Pin the repo from your GitHub profile page (Customize your pins). The `gh` CLI has no pin command.
