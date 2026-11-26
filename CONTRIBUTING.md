# Contributing

Thanks for helping improve the image provenance check.

## Ground rules
- **The tool only escalates.** It must never issue a "cleared" or "safe" verdict. The best outcome is `USABLE_AFTER_RECORD`.
- Policy lives in `rules/*.json`. Prefer changing rules over changing code.
- Fuzzy judgement (looking at the image, tracing sources) belongs to the agent or a person; deterministic checks belong in `scripts/imgrights.py`.

## Workflow
1. Branch from `main` (`feature/<short-name>` or `fix/<short-name>`).
2. Make your change and add or update a case in `tests/run_tests.py`.
3. Run the tests: `pip install -r requirements.txt && python tests/run_tests.py`. They must report `0 failure(s)`.
4. Update `CHANGELOG.md` under **Unreleased**.
5. Open a pull request using the template.

## Rule changes
When adding domains, filename patterns or license entries, include a link or example showing why in the pull request.

## Not legal advice
This tool supports a human process and is not legal advice.
