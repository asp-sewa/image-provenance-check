---
name: image-provenance-check
description: Check whether an image is safe to publish (website, post, newsletter, video). Gathers ownership evidence (file name, metadata, download origin, OCR credits), traces the original source, verifies the license, and records the result. Use when someone asks "can we use this image", to check image rights, copyright, watermark or license, or to find a safe replacement image.
---

# Image provenance check

Purpose: before any image is published we must be able to say **where it came from and under what license**. If we cannot, we do not use it. This skill is a working procedure, not legal advice.

**Hard rule: never say an image is "cleared", "safe" or "OK".** "No warning found" is not clearance. The best possible outcome is `USABLE_AFTER_RECORD`: a permitted license verified on the original page, people and logos confirmed absent, and the evidence logged.

## How the work is split

- **Deterministic (the script decides, you do not override):** file-name patterns, metadata fields, Zone.Identifier download origin, OCR credit text, license normalisation against the license policy table, the verdict, and the image-log record. All in `scripts/imgrights.py`; policy lives in `rules/*.json`.
- **Fuzzy (you do, then report what you saw):** looking at the image for watermarks/logos/people/children, tracing the reverse-image trail to the original page, judging whether a page is the original source, and reading license text the script could not parse.

Never let a fuzzy judgement lift a verdict the script set to BLOCK or REPLACE. You may only move an image forward by supplying *evidence* (`--license`, `--source-url`, `--author`) the script then re-evaluates.

## Procedure

Resolve `scripts/imgrights.py` relative to this skill folder. Python 3 + Pillow required; `exiftool` and `tesseract` are used if on PATH.

### 1. Run the automatic checks (guide steps 1-4)
```
python scripts/imgrights.py check <image-or-folder> [--out report.json]
```
This covers file name, metadata, Zone.Identifier (Windows PC only) and OCR. Read the JSON `verdict`, `reasons` and `next`.
- `BLOCK`: stop. Tell the user why. Offer a replacement from Part 2 sources (step 7).
- `TRACE_REQUIRED`: continue to steps 4-6.
- If `zone.status` is `unavailable` or `absent`, say so plainly. Uploaded/emailed/zipped files lose it; it means nothing either way.

### 2. Look at the image yourself (guide step 4, fuzzy part)
Open the image at full size and follow `references/visual-review.md`. Report: watermarks, tiled text, corner marks, credit lines, logos/brands/artwork, identifiable people (especially children), and context that could mislead (disaster relief, fundraising). Record `--people none|yes|unknown` and `--logos none|yes|unknown`. If you cannot view the image, use `unknown`.

### 3. Metadata caveat
Empty metadata is normal for web/social images. A filled creator/copyright/credit field is direct evidence of ownership.

### 4. Trace the original (guide step 5)
Reverse-image search is the weakest automated link: Google Lens, Yandex and Bing have no free official API, TinEye's is paid. Use whatever this environment offers, in order:
1. A configured reverse-search tool/API or browser agent (Claude in Chrome / built-in browser, ChatGPT agent mode, etc.).
2. Otherwise give the user the engine list (Google Lens, Bing, Yandex, TinEye) and ask them to paste back the best candidate page URLs.

Reading results: many sites using a picture proves nothing about rights. Follow the trail to the **earliest and largest** copy (TinEye: sort Oldest / Biggest). Stock agency, news outlet or photographer portfolio = owned, do not use. Free-license platform = open the original page and confirm. **No matches does not mean safe.**

To check that a candidate image really is the same picture: `python scripts/imgrights.py compare <local> <downloaded-candidate>` (hash distance; crops and overlays defeat it, so a large distance is not proof of difference).

### 5. Verify the license on the original page (Part 2)
```
python scripts/imgrights.py license-page --url <original-page-url>      # or --html-file saved.html
```
The script extracts `rel=license` links, Creative Commons URLs, JSON-LD license, author metadata, and maps each to the license policy action. Then **you** must confirm: it is the original page (not a re-host saying "free"); the uploader is the actual photographer (Flickr especially); the license applies to this image, not the site generally. If the script finds nothing, read the page text yourself; if still unclear, the answer is "not verified".

Policy summary (authoritative copy: `rules/license_policy.json`): CC0/public domain yes; CC BY yes with credit; CC BY-SA ask IT first; CC BY-NC no; CC BY-ND unedited only; Pexels/Unsplash/Pixabay are custom licenses, read them.

### 6. Get the verdict
Re-run `check` with the evidence:
```
python scripts/imgrights.py check <image> --license "CC BY 4.0" --source-url <page> --author "<name>" --people none --logos none
```
If the trail was exhausted with nothing, run with `--trace-done` (verdict becomes REPLACE).

Verdicts and what you tell the user:
| Verdict | Meaning | Say |
|---|---|---|
| BLOCK | owner/stock/news/credit evidence | Do not use; replace or buy a license. |
| REPLACE | no verified license, or license not permitted | Do not use; replace. |
| HUMAN_REVIEW | people/children/logos, CC BY-SA, or metadata claims alongside a license | Needs second review from IT before use; list exactly why. |
| TRACE_REQUIRED | nothing found yet, or trace incomplete | Not cleared; continue tracing. |
| USABLE_AFTER_RECORD | permitted license verified, people/logos none | Usable once recorded; state the attribution/edit conditions. |

### 7. Record before publishing
Take a screenshot of the license page, then:
```
python scripts/imgrights.py record --file <name> --used-in "<page or post>" --source-url <url> --author "<name>" --license "<license>" --license-url <url> --checked-by "<name>" --screenshot <png> --log image_log.csv
```
The script refuses an incomplete record. Never record an image whose verdict was not `USABLE_AFTER_RECORD`/`HUMAN_REVIEW`-approved. If the shared log is a Zoho Sheet, append the same columns there (`file, used_in, source_url, author, license, license_url, date_checked, checked_by, screenshot, verdict, conditions`).

### Finding safe images instead (guide Part 2)
Prefer safe sources over checking the open web: Google Images (Tools > Usage rights > Creative Commons; never "Commercial & other licenses"), Openverse, Wikimedia Commons, Pexels/Unsplash/Pixabay, Flickr CC, Smithsonian/NASA/Library of Congress, our own photography (needs written photographer release and consent from identifiable people), paid stock (keep the receipt). Always open the individual image page and read the license before downloading. Prefer images without recognisable faces.

## Final answer format
Give: verdict (one of the five words), the 2-4 evidence items behind it, what you could not check (e.g. "Zone.Identifier unavailable in this environment", "reverse search done manually"), the attribution/edit conditions if any, and the next action. Keep it short; attach the JSON report on request.

## Environment notes
- Zone.Identifier (download origin) works only when this runs on the staff Windows PC against the original downloaded file. In a cloud sandbox or chat upload it is lost.
- Network may be restricted in hosted sandboxes; `license-page --url` can fail there. Fall back to `--html-file` with a saved page or read the page via a browser tool.
- Edit `rules/*.json` to change policy; no code change needed.
