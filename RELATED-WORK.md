# Related work (searched 2026-10-07, about 15 minutes, read-only)

Queries: "Claude Code" Blender MCP video trailer; blender-mcp agent long-running iterative render loop;
AI agent edits video Premiere/After Effects/DaVinci Resolve MCP; autonomous agent overnight video
production critic loop; Claude agent PROGRESS.md memory file long-running creative project;
AI-generated Apollo 11 trailer public domain NASA footage; plus Anthropic's long-running harness post.

Compared on four points:
- (a) several creative apps driven over MCP in one pipeline;
- (b) an unattended multi-hour loop with a durable memory file;
- (c) a separate critic agent plus revert-on-regression;
- (d) real archival media with licence tracking plus a raw-vs-final comparison.

Every link below was opened on the search date.

| Project | What it does | a | b | c | d |
|---|---|---|---|---|---|
| [Anthropic, "Effective harnesses for long-running agents"](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (2025-11-26) | initializer agent + repeated coding sessions that read and write `claude-progress.txt` and commit to git; built a web app | – | **yes** (the pattern MOONSHOT's PROGRESS.md follows) | git for reverts, self-testing, no separate critic | – |
| [Kinocut (KyaniteLabs)](https://github.com/KyaniteLabs/kinocut) | guardrailed ffmpeg video-editing MCP server with quality and release checkpoints and provenance receipts | one tool (ffmpeg) | – | quality gates, human review recommended | provenance receipts, not licence/raw-vs-final |
| [DaVinci Resolve MCP (Tooflex)](https://github.com/Tooflex/davinci-resolve-mcp) | 32 MCP tools to edit, grade and render in Resolve | one app | – | – | – |
| [Adobe Premiere Pro MCP (hetpatel-11)](https://glama.ai/mcp/servers/@hetpatel-11/Adobe_Premiere_Pro_MCP/blob/b9fa9862ecb7be8d717cd63c4b32be594e13bd6c/README.md) | bridge to a 280-tool Premiere catalogue | one app | – | – | – |
| [Blender MCP server v2 (StraySpark)](https://www.strayspark.studio/blog/blender-mcp-server-v2-vision-async-jobs-cc0-assets) | 228 Blender tools; the agent renders a preview, looks and adjusts; async jobs; CC0 Poly Haven/ambientCG assets | one app | – | vision feedback loop, no separate critic | CC0 assets, no tracking described |
| [invideo, "automated overnight AI video"](https://invideo.io/faq/how-do-you-set-up-an-automated-overnight-ai-video/) | overnight chain of sub-agents (producer → storyboard → render → QA) with a maker-checker pass | generation models, not editing apps | overnight, no memory file described | **QA/critic agent** | generated video only, no archival footage |

Not included: links that 404'd (MagellanTV "Apollo's New Moon" trailer page) and pages I did not open.

**Reading:** each of the four pieces exists elsewhere:
- the progress-file loop (Anthropic's harness);
- MCP control of a single editor (Resolve, Premiere, Blender, ffmpeg);
- critic/QA agents in generated-video pipelines (invideo).

**MOONSHOT doesn't fully meet (a) either.** Only EffectCraft was driven over MCP, and only in
v1–v2. The final pipeline is ffmpeg/Python plus headless Blender scripts. So the README must not
claim the four-way combination. The honest line is narrower: I haven't found another public run
that pairs (b) a multi-hour progress-file loop with (c) blind-A/B keep/revert and (d) licence-logged
archival media with a raw-vs-final cut. That covers a 15-minute search, not the field.
