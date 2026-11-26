# image-provenance-check (Agent Skill)

One folder, three platforms. It follows the open Agent Skills layout (SKILL.md + scripts/ + rules/ + references/).

Requirements on the machine that runs it: Python 3.8+, Pillow (`pip install pillow`). Optional but recommended: exiftool, tesseract.
Run it on the staff Windows PC against the ORIGINAL downloaded file so Zone.Identifier works.

## Install
| Platform | Where to put the folder |
|---|---|
| Claude (Claude Code / desktop) | `~/.claude/skills/image-provenance-check/` (or project `.claude/skills/`). Claude.ai: upload the zip under Settings > Capabilities > Skills. |
| ChatGPT desktop / Codex CLI | `~/.agents/skills/image-provenance-check/` or repo `.agents/skills/`. For web/mobile ChatGPT, package it inside a plugin. |
| Gemini CLI | `~/.gemini/skills/image-provenance-check/` (or `~/.agents/skills/`). Agent Skills may need enabling in Gemini CLI settings; then `/skills reload`. |

Or run `install.ps1` (Windows) / `install.sh` (macOS/Linux) to copy to all of the above.

## Use
Ask the agent: "Check this image for rights: <path>". Or directly:
`python scripts/imgrights.py check <file>`; `license-page`, `compare`, `record` as described in SKILL.md.

## Customise (no code changes)
`rules/filename_patterns.json`, `domains.json` (add your organization's own storage hostnames and org names; list org names in `own_org_patterns`, lowercase), `license_policy.json`, `ocr_patterns.json`.

## Test
`python tests/run_tests.py`

## Known limits
- Reverse image search is not automated (no free official APIs); the agent or a person traces the trail.
- Zone.Identifier only exists on Windows for browser-downloaded files.
- OCR misses stylised/faint marks. Visual review is by the model/person.
- Not legal advice.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md). Changes are tracked in [CHANGELOG.md](CHANGELOG.md). Report security issues per [SECURITY.md](SECURITY.md).

## License
Released into the public domain under [The Unlicense](LICENSE).
