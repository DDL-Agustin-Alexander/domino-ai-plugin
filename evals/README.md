# Behaviour tests for the Domino plugin

`claude plugin eval` runs every directory here as one case: `prompt.md` (frontmatter plus the
user prompt), optional `case.yaml` naming a `fixture.sh` that seeds the working directory, and
`graders/*.md`. Format reference: https://code.claude.com/docs/en/plugin-evals. Each run is a real
model call billed to your account; results land in `results/` (git-ignored).

## What the suite covers

| Tag | Cases | Checks |
|---|---|---|
| `trigger` | one or more per skill | The skill fires on a natural request (`tool_used: Skill`) and the answer is correct |
| `negative` | 5 | No Domino skill fires on a non-Domino request, including the word "domino" in a board game |
| `disambiguation` | 15 | For overlapping skills, the right one fires and the neighbour does not (`min: 0`, `max: 0`, `arm: both`) |
| `compat` | 1 | The answer is gated on the Domino version named in the prompt |

Every case also carries its skill name as a tag (`domino-jobs`, `netapp-volumes`, ...), so
`--tag domino-jobs` runs the cases for one skill.

Overlapping pairs with strict disambiguation cases: `domino-model-endpoints` / `domino-model-serving`,
`domino-apps` / `domino-app-init` / `domino-debug-proxy`, `domino-experiment-tracking` /
`domino-experiment-setup`, `domino-genai-tracing` / `domino-trace-setup`, `domino-datasets` /
`netapp-volumes` / `domino-data-sdk`, `domino-api-intro` / `domino-python-sdk` (one direction only:
AGENTS.md asks for `domino-api-intro` to load alongside the SDK skill, so the SDK case allows it).

## Grading rules

Correctness graders check Domino's documented behaviour, not the current skill text: routes and
field names come from the public API specs, python-domino and domino-data method names from their
source, paths, roles, env vars and UI steps from docs.domino.ai. A case that fails because a skill
still carries an invented method or route is doing its job.

- Content checks target the model's deliverable, never the session trace: `target: last_message`
  for answer-only prompts (which say "put the code in your reply"), and `target: { source: file,
  path: ... }` for file-writing prompts, which name the file they expect. The trace includes tool
  results, so a regex on `trace` would also match the SKILL.md text the model read (an invented
  method quoted by the skill would fail a model that correctly ignored it, and a documented fact
  quoted by the skill would pass a model that never used it). `trace` is used only by `tool_used`.
- `regex` graders with `match: not_contains` catch invented SDK methods, invented fields, legacy
  API-key *usage* (a prose mention that the key is deprecated passes) and JWT `iss` scraping.
- `llm` graders carry a PASS/FAIL rubric; where the judged content is a file the grader sets
  `focus: { source: file, path: ... }`.
- The `skill-fired` grader is excluded from the score under the default `with-without` ablation
  (it can never pass without the plugin); it still shows as an indicator. Under `--ablation none`
  it is scored.

Sandbox facts that shape the cases: the run cannot `Read` the plugin's own files, so a skill is
exercised through its SKILL.md and whatever the model already knows (sibling reference files and
`assets/` templates are out of reach; the model reports "access denied" when it tries); the always-on
`rules/domino.md` is loaded, so a request answerable from it alone may be answered in one turn
without loading any skill.

## Running

```bash
# one case, one run, no baseline arm (cheapest iteration; about $0.10 to $0.50 per case)
claude plugin eval . --case start-job-via-rest-and-schedule --runs 1 --ablation none --no-publish --scaffold --allow-tools Write Edit

# one skill or one category
claude plugin eval . --tag domino-datasets --runs 1 --ablation none --no-publish --scaffold --allow-tools Write Edit
claude plugin eval . --tag negative --runs 1 --ablation none --no-publish

# full suite, default three runs plus the no-plugin baseline (46 cases; budget accordingly)
claude plugin eval . --scaffold --allow-tools Write Edit --no-publish -j 3 --max-cost-usd 60 --json results.json
```

`--scaffold` runs each case's `fixture.sh` (author-supplied bash, so only on cases you trust) and
`--allow-tools Write Edit` grants the write tools the file-writing cases list. Fixtures contain no
credentials; ids in prompts are placeholders. The plugin's MCP servers are not started during evals
(no mocks are defined), which is what `run-job-without-mcp` relies on.

## Adding a case

Copy a neighbouring directory. Name the case after the request, not the skill; tag it with the
skill name and `trigger`, `negative` or `disambiguation`; put the skill-firing check in
`graders/skill-fired.md` and keep correctness graders grounded in a docs.domino.ai page, a spec
route or an SDK method you verified.
