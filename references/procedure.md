# Source procedure (condensed from "Checking Image Rights Before You Publish", Oct 2026)

Part 1 evidence steps (each only adds evidence; none clears an image alone):
1. File name + file properties (Authors, Copyright, Title, Subject).
2. Full EXIF/IPTC/XMP metadata (creator, credit, source, usage terms, license). Empty = meaningless.
3. Download origin via NTFS Zone.Identifier (ReferrerUrl = page, HostUrl = file). Lost on email/chat/zip/USB/re-save.
4. Watermarks and visible credits; detectors are hints only.
5. Reverse image search (Google, Bing, Yandex, TinEye). TinEye: sort Oldest and Biggest. Trace to the ORIGINAL; many copies prove nothing; no matches is not safe.

Decision table:
- copyright/credit field, stock/agency name, stock/news source, visible watermark -> do not use
- traced to original page with clear free license -> usable after recording
- no metadata/source/matches, or many copies and no clear original -> unusable
- clear license but identifiable people (esp. children), logos, artwork -> second review

Part 2: prefer safe sources; read license on the individual page; Google "Commercial & other licenses" is NOT a free option; CC table in rules/license_policy.json; people/logos/context rules; keep a record (file + use, source link + author, license + link, date + checker, screenshot).

Mapping to this skill: steps 1-4 -> `imgrights.py check`; step 5 -> agent/human + `compare`; Part 2 license -> `license-page`; record -> `record`.
