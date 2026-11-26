# Visual review checklist (fuzzy step, done by the model or a person)

OCR and file checks cannot see these. Look at the image at full size, then at each corner and edge, and report what you saw, not what you assume.

1. **Watermarks**: tiled/diagonal text, semi-transparent logos, corner marks, banner strips along the bottom. A faint watermark can be invisible at thumbnail size.
2. **Credit lines**: "Photo: ...", "(c) ...", agency names along an edge or in a caption strip.
3. **People**: any identifiable face? Children? (A copyright license does not give consent. Children always need confirmed release or explicit platform allowance.) Prefer replacing with an image without recognisable faces.
4. **Logos, brands, products, artwork, signage**: prominent trademarks or another creator's artwork.
5. **Context**: would the use imply these people support the organization, or misrepresent the situation (disaster relief, fundraising)?
6. **Signs of stock origin**: unnaturally staged, uniform lighting, typical stock framing. Hint only; never a basis to clear.

Output: `--people none|yes|unknown`, `--logos none|yes|unknown`, plus one line per finding. If unable to view the image, say so and use `unknown` (this forces HUMAN_REVIEW).
