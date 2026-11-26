#!/usr/bin/env python3
"""imgrights - deterministic evidence + verdict engine for image-rights checks.

Subcommands
  check         gather evidence for image file(s) and issue a verdict
  license-page  extract license/author candidates from a source page (URL or saved HTML)
  compare       perceptual-hash distance between two images (is this candidate the same picture?)
  record        validate and append an entry to the shared image log (CSV)

Design rule: this tool can only ESCALATE. It never issues "cleared". The best
verdict is USABLE_AFTER_RECORD, and only when a permitted license was verified
on the original page, people/logos were confirmed absent, and the record is complete.

Dependencies: Python 3.8+, Pillow. Optional: exiftool, tesseract (both on PATH).
"""
import argparse, csv, datetime, glob, html, json, os, re, shutil, subprocess, sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(os.path.dirname(HERE), "rules")
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp", ".heic"}

VERDICT_ORDER = ["BLOCK", "REPLACE", "HUMAN_REVIEW", "TRACE_REQUIRED", "USABLE_AFTER_RECORD"]


def load_rule(name):
    with open(os.path.join(RULES, name), encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------- helpers
def host_of(url):
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def host_matches(host, suffixes):
    return any(host == s or host.endswith("." + s) for s in suffixes)


def classify_url(url, domains):
    h = host_of(url)
    if not h:
        return None
    for kind in ("stock", "news", "free_license", "own_storage"):
        if host_matches(h, domains[kind]):
            return kind
    return "other"


# ----------------------------------------------------------- evidence steps
def step_filename(path, patterns):
    name = os.path.basename(path)
    hits = {"block": [], "trace": []}
    for kind in ("block", "trace"):
        for p in patterns[kind]:
            if re.search(p["pattern"], name, re.I):
                hits[kind].append({"id": p["id"], "label": p["label"]})
    return {"name": name, "block_hits": hits["block"], "trace_hits": hits["trace"]}


META_KEYS = {
    "creator": ["Artist", "Creator", "By-line", "Author", "XPAuthor", "Photographer"],
    "copyright": ["Copyright", "CopyrightNotice", "Rights", "XPCopyright"],
    "credit": ["Credit", "CreditLine"],
    "source": ["Source"],
    "usage_terms": ["UsageTerms", "RightsUsageTerms", "WebStatement", "License", "LicenseURL"],
}


def _exiftool(path):
    exe = shutil.which("exiftool")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-json", "-G0", "-a", "-u", path], capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout)[0]
        return {k.split(":", 1)[-1]: str(v) for k, v in data.items()}
    except Exception:
        return None


def _pillow_meta(path):
    meta = {}
    try:
        from PIL import Image, ExifTags
        with Image.open(path) as im:
            ex = im.getexif()
            for tag, val in ex.items():
                meta[ExifTags.TAGS.get(tag, str(tag))] = str(val)
            try:  # IFD0 sub-dirs often hold Copyright
                for tag, val in ex.get_ifd(0x8769).items():
                    meta.setdefault(ExifTags.TAGS.get(tag, str(tag)), str(val))
            except Exception:
                pass
            for k, v in (im.info or {}).items():
                if isinstance(v, str) and k.lower() not in ("icc_profile",):
                    meta.setdefault(k, v)
    except Exception as e:
        meta["_pillow_error"] = str(e)
    # XMP packet scan (works for any container that embeds a plain XMP block)
    try:
        with open(path, "rb") as f:
            raw = f.read(8_000_000)
        m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", raw, re.S)
        if m:
            x = m.group(0).decode("utf-8", "replace")
            for tag in ("dc:creator", "dc:rights", "photoshop:Credit", "photoshop:Source",
                        "xmpRights:UsageTerms", "xmpRights:WebStatement", "cc:license", "plus:Licensor"):
                mm = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), x, re.S)
                if mm:
                    meta["XMP-" + tag] = re.sub(r"<[^>]+>", " ", mm.group(1)).strip()
                    continue
                mm = re.search(r'%s="([^"]*)"' % tag, x)
                if mm:
                    meta["XMP-" + tag] = mm.group(1)
    except Exception:
        pass
    return meta


def step_metadata(path, domains):
    tool = "exiftool"
    meta = _exiftool(path)
    if meta is None:
        tool, meta = "pillow+xmp-scan", _pillow_meta(path)
    found = {}
    for field, keys in META_KEYS.items():
        for k, v in meta.items():
            kk = k.replace("XMP-", "").split(":")[-1]
            if any(kk.lower().endswith(x.lower()) for x in keys) and v.strip():
                found.setdefault(field, []).append("%s=%s" % (k, v.strip()[:200]))
    own = [p for p in domains["own_org_patterns"]
           if any(p in v.lower() for vals in found.values() for v in vals)]
    return {"tool": tool, "fields": found, "empty": not found, "own_org_match": bool(own),
            "note": "Empty metadata means nothing: most web/social images are stripped."}


def parse_zone(text):
    d = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def step_zone(path, domains):
    if os.name != "nt":
        return {"status": "unavailable", "note": "Zone.Identifier exists only on Windows/NTFS files downloaded by a browser. "
                "Run this tool on the staff PC (not a cloud sandbox/upload) to use this step."}
    try:
        with open(path + ":Zone.Identifier", "r", encoding="utf-8", errors="replace") as f:
            z = parse_zone(f.read())
    except OSError:
        return {"status": "absent", "note": "No Zone.Identifier: lost via email/chat/zip/USB/re-save, or not browser-downloaded. Means nothing."}
    return zone_result(z, domains)


def zone_result(z, domains):
    urls = [u for u in (z.get("ReferrerUrl"), z.get("HostUrl")) if u]
    kinds = sorted({classify_url(u, domains) for u in urls if classify_url(u, domains)})
    return {"status": "found", "referrer_url": z.get("ReferrerUrl"), "host_url": z.get("HostUrl"),
            "classes": kinds}


def _ocr_variants(path):
    """Yield preprocessed PIL images: credits/watermarks sit on edges and on busy backgrounds."""
    from PIL import Image, ImageOps
    with Image.open(path) as im0:
        g = ImageOps.autocontrast(im0.convert("L"))
    w, h = g.size
    strips = {"full": g, "bottom": g.crop((0, int(h * .70), w, h)), "top": g.crop((0, 0, w, int(h * .30))),
              "left": g.crop((0, 0, int(w * .30), h)), "right": g.crop((int(w * .70), 0, w, h))}
    for name, im in strips.items():
        if max(im.size) < 1800:
            sc = 1800 / max(im.size)
            im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))))
        yield name + ":plain", im
        yield name + ":inverted", ImageOps.invert(im)
        yield name + ":threshold", im.point(lambda v: 255 if v > 170 else 0)
        yield name + ":threshold-dark", im.point(lambda v: 255 if v < 90 else 0)


def step_ocr(path, ocr_patterns):
    exe = shutil.which("tesseract")
    if not exe:
        return {"status": "unavailable", "hits": [], "text": ""}
    import tempfile
    texts = []
    try:
        for name, im in _ocr_variants(path):
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False); tmp.close()
            im.save(tmp.name)
            try:
                for psm in ("11", "6"):
                    out = subprocess.run([exe, tmp.name, "stdout", "--psm", psm], capture_output=True, text=True, timeout=45)
                    texts.append(out.stdout)
            finally:
                os.unlink(tmp.name)
    except Exception as e:
        return {"status": "error", "error": str(e), "hits": [], "text": ""}
    text = "\n".join(t.strip() for t in texts if t.strip())
    hits = [p for p in ocr_patterns["patterns"] if re.search(p, text, re.I)]
    return {"status": "ok", "hits": hits, "text": text[:500],
            "note": "OCR misses stylised, faint or tiny marks. No hit is not clearance."}


def dhash(path, size=8):
    from PIL import Image
    with Image.open(path) as im:
        g = im.convert("L").resize((size + 1, size))
        px = list(g.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (px[r * (size + 1) + c] > px[r * (size + 1) + c + 1])
    return "%016x" % bits


def step_image(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return {"format": im.format, "size": list(im.size), "dhash": dhash(path)}
    except Exception as e:
        return {"error": str(e)}


# --------------------------------------------------------- license handling
def normalise_license(s):
    """Return a policy key from free text or a license URL; None if unrecognised."""
    if not s:
        return None
    t = s.strip().lower()
    m = re.search(r"creativecommons\.org/(licenses|publicdomain)/([a-z\-]+)/", t)
    if m:
        t = ("cc0" if m.group(2) == "zero" else "public-domain" if m.group(2) == "mark" else "cc-" + m.group(2))
    t = re.sub(r"[\s_]+", "-", t)
    t = re.sub(r"-?(\d\.\d|v\d)(-.*)?$", "", t) if t.startswith("cc") else t
    aliases = {"cc0": "cc0", "cc-0": "cc0", "pd": "public-domain", "publicdomain": "public-domain",
               "public-domain": "public-domain", "pdm": "public-domain", "by": "cc-by", "cc-by": "cc-by",
               "ccby": "cc-by", "cc-by-sa": "cc-by-sa", "cc-by-nc": "cc-by-nc", "cc-by-nd": "cc-by-nd",
               "cc-by-nc-sa": "cc-by-nc-sa", "cc-by-nc-nd": "cc-by-nc-nd"}
    if t in aliases:
        return aliases[t]
    if "public-domain" in t or "publicdomain" in t:
        return "public-domain"
    for k in ("pexels", "unsplash", "pixabay"):
        if k in t:
            return k
    if t in ("paid-stock", "own-photo"):
        return t
    return None


def license_action(lic, policy):
    if lic is None:
        return policy.get("unknown_action", "deny"), "License not recognised; treat as not permitted until IT confirms."
    e = policy["licenses"].get(lic)
    if not e:
        return policy.get("unknown_action", "deny"), "License not in policy table."
    return e["action"], e["note"]


def parse_license_html(doc):
    """Deterministic first pass over a page: rel=license, CC links, JSON-LD, author meta."""
    out = {"license_urls": [], "license_text_hits": [], "authors": [], "canonical": None, "title": None}
    for m in re.finditer(r'<(?:a|link)\b[^>]*\brel=["\'][^"\']*license[^"\']*["\'][^>]*>', doc, re.I):
        h = re.search(r'href=["\']([^"\']+)', m.group(0), re.I)
        if h:
            out["license_urls"].append(html.unescape(h.group(1)))
    for m in re.finditer(r'https?://creativecommons\.org/(?:licenses|publicdomain)/[a-z\-]+/[\d.]*/?', doc, re.I):
        out["license_urls"].append(m.group(0))
    for m in re.finditer(r'"license"\s*:\s*"([^"]+)"', doc):
        out["license_urls"].append(m.group(1))
    for k in ("Pexels License", "Unsplash License", "Pixabay Content License", "Pixabay License", "Public Domain Mark", "CC0"):
        if re.search(re.escape(k), doc, re.I):
            out["license_text_hits"].append(k)
    for m in re.finditer(r'<meta[^>]+(?:name|property)=["\'](?:author|article:author|og:author)["\'][^>]*content=["\']([^"\']+)', doc, re.I):
        out["authors"].append(html.unescape(m.group(1)))
    for m in re.finditer(r'"author"\s*:\s*(?:\{[^}]*"name"\s*:\s*"([^"]+)"|"([^"]+)")', doc):
        out["authors"].append(m.group(1) or m.group(2))
    c = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', doc, re.I)
    out["canonical"] = c.group(1) if c else None
    t = re.search(r"<title[^>]*>(.*?)</title>", doc, re.I | re.S)
    out["title"] = html.unescape(t.group(1)).strip() if t else None
    for k in ("license_urls", "license_text_hits", "authors"):
        out[k] = list(dict.fromkeys(out[k]))
    return out


def cmd_license_page(a):
    policy = load_rule("license_policy.json")
    if a.html_file:
        doc = open(a.html_file, encoding="utf-8", errors="replace").read()
        src = a.html_file
    else:
        import urllib.request
        req = urllib.request.Request(a.url, headers={"User-Agent": "Mozilla/5.0 imgrights/1.0"})
        doc = urllib.request.urlopen(req, timeout=30).read(3_000_000).decode("utf-8", "replace")
        src = a.url
    p = parse_license_html(doc)
    cands = []
    for u in p["license_urls"] + p["license_text_hits"]:
        lic = normalise_license(u)
        act, note = license_action(lic, policy)
        cands.append({"raw": u, "license": lic, "policy_action": act, "policy_note": note})
    res = {"source": src, "page": p, "candidates": cands,
           "needs_llm_or_human": ["Confirm this is the ORIGINAL page, not a re-host saying 'free'.",
                                  "Confirm the uploader/author is the actual photographer.",
                                  "Confirm the license text applies to THIS image, not the site generally."]}
    print(json.dumps(res, indent=2, ensure_ascii=False))


# ------------------------------------------------------------ verdict logic
def decide(ev, a, policy):
    hard, soft, reasons, conditions = [], [], [], []
    fn, md, zn, oc = ev["filename"], ev["metadata"], ev["zone"], ev["ocr"]
    for h in fn["block_hits"]:
        hard.append("filename: " + h["label"])
    if zn.get("status") == "found":
        for c in zn["classes"]:
            if c in ("stock", "news"):
                hard.append("download source is a %s site (%s)" % (c, zn.get("referrer_url") or zn.get("host_url")))
    if oc.get("hits"):
        hard.append("visible credit/watermark text found by OCR: %s" % oc["hits"][:4])
    if md["fields"].get("copyright") or md["fields"].get("credit") or md["fields"].get("creator"):
        if md["own_org_match"]:
            soft.append("metadata names our organisation: confirm release/consent (own material)")
        else:
            soft.append("metadata carries creator/copyright/credit: " + "; ".join(
                v for k in ("copyright", "credit", "creator") for v in md["fields"].get(k, []))[:300])

    trace_hint = [h["label"] for h in fn["trace_hits"]]
    if zn.get("status") == "found" and "free_license" in zn["classes"]:
        trace_hint.append("download source is a free-license platform: verify license on that page")
    if zn.get("status") == "found" and "own_storage" in zn["classes"]:
        trace_hint.append("download came from our own storage: origin still unknown, keep investigating")
    ev["trace_hints"] = trace_hint

    lic = normalise_license(a.license) if a.license else None
    action = note = None
    if a.license:
        action, note = license_action(lic, policy)

    if hard:
        return "BLOCK", hard + soft, ["Do not use. Replace it, or buy a license from the owner."]
    if soft and not (a.license and action in ("allow", "allow_attribution", "unedited_only", "platform")):
        return "BLOCK", soft, ["Creator/copyright/credit evidence found and no verified permissive license. Do not use."]
    if not a.license:
        if a.trace_done:
            return "REPLACE", ["Trace completed with no verified license/original source."], ["Replace the image."]
        return "TRACE_REQUIRED", ["No ownership warning found. That is NOT clearance."], \
            ["Run the reverse-image trail (see SKILL.md step 5), find the original page, then re-run with --license/--source-url/--author."]
    # a license was claimed from tracing
    if action == "deny":
        return "REPLACE", ["License '%s' not permitted: %s" % (a.license, note)], ["Replace the image."]
    missing = [n for n, v in (("--source-url", a.source_url), ("--author", a.author)) if not v and lic not in ("cc0", "public-domain")]
    if missing:
        return "TRACE_REQUIRED", ["Incomplete trace: missing " + ", ".join(missing)], ["Provide the missing fields from the original page."]
    review = []
    if soft:
        review.append("Metadata claims exist alongside the license: " + soft[0])
    if a.people != "none":
        review.append("People %s: a license does not give consent, especially for children." % ("present" if a.people == "yes" else "not yet checked"))
    if a.logos != "none":
        review.append("Logos/artwork/products %s." % ("present" if a.logos == "yes" else "not yet checked"))
    if action == "ask_it":
        review.append(note)
    if review:
        return "HUMAN_REVIEW", review, ["Get a second review from IT before use."]
    if action == "allow_attribution":
        conditions.append("Attribution required: Title, Author, Source link, License. " + note)
    if action == "unedited_only":
        conditions.append("Use unedited only (no crop, filter or text overlay). " + note)
    if action == "platform":
        conditions.append(note)
    conditions.append("Run `record` to save the evidence to the image log BEFORE publishing.")
    return "USABLE_AFTER_RECORD", ["Permitted license verified on original page (as reported by the checker)."], conditions


def collect(path, a, rules):
    ev = {"file": path}
    ev["filename"] = step_filename(path, rules["fn"])
    ev["metadata"] = step_metadata(path, rules["dom"])
    ev["zone"] = step_zone(path, rules["dom"]) if not a.zone_text else zone_result(parse_zone(a.zone_text), rules["dom"])
    ev["ocr"] = step_ocr(path, rules["ocr"]) if not a.no_ocr else {"status": "skipped", "hits": []}
    ev["image"] = step_image(path)
    return ev


def cmd_check(a):
    rules = {"fn": load_rule("filename_patterns.json"), "dom": load_rule("domains.json"), "ocr": load_rule("ocr_patterns.json")}
    policy = load_rule("license_policy.json")
    files = []
    for p in a.paths:
        if os.path.isdir(p):
            files += sorted(f for f in glob.glob(os.path.join(p, "**", "*"), recursive=True)
                            if os.path.splitext(f)[1].lower() in IMG_EXT)
        else:
            files += glob.glob(p) or [p]
    if not files:
        sys.exit("no image files found")
    results = []
    for f in files:
        ev = collect(f, a, rules)
        v, why, nxt = decide(ev, a, policy)
        ev["verdict"], ev["reasons"], ev["next"] = v, why, nxt
        ev["needs_visual_review"] = ["watermarks/logos/corner marks (OCR misses faint ones)",
                                     "identifiable people, especially children",
                                     "brands, logos, artwork, context/misrepresentation"]
        ev["reverse_search_engines"] = ["Google Lens", "Bing", "Yandex", "TinEye (sort Oldest / Biggest)"]
        results.append(ev)
    out = {"generated": datetime.datetime.now().isoformat(timespec="seconds"), "results": results}
    s = json.dumps(out, indent=2, ensure_ascii=False)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(s)
    print(s)
    worst = min(VERDICT_ORDER.index(r["verdict"]) for r in results)
    sys.exit(0 if VERDICT_ORDER[worst] == "USABLE_AFTER_RECORD" else 2)


def cmd_compare(a):
    h1, h2 = dhash(a.a), dhash(a.b)
    d = bin(int(h1, 16) ^ int(h2, 16)).count("1")
    print(json.dumps({"dhash_a": h1, "dhash_b": h2, "hamming": d,
                      "reading": "likely same picture" if d <= 10 else "probably different (or heavily edited/cropped)",
                      "caveat": "Crops and overlays change hashes. A big distance does not prove difference."}, indent=2))


RECORD_FIELDS = ["file", "used_in", "source_url", "author", "license", "license_url", "date_checked", "checked_by", "screenshot", "verdict", "conditions"]


def cmd_record(a):
    policy = load_rule("license_policy.json")
    lic = normalise_license(a.license)
    pd = lic in ("cc0", "public-domain")
    req = {"file": a.file, "used_in": a.used_in, "source_url": a.source_url, "license": a.license,
           "license_url": a.license_url, "checked_by": a.checked_by, "screenshot": a.screenshot}
    if not pd:
        req["author"] = a.author
    miss = [k for k, v in req.items() if not v]
    if miss:
        sys.exit("REFUSED: record incomplete, missing: " + ", ".join(miss))
    if not os.path.exists(a.screenshot):
        sys.exit("REFUSED: screenshot file not found: " + a.screenshot)
    action, note = license_action(lic, policy)
    if action == "deny":
        sys.exit("REFUSED: license not permitted by policy: " + note)
    row = {"file": a.file, "used_in": a.used_in, "source_url": a.source_url, "author": a.author or "",
           "license": a.license, "license_url": a.license_url,
           "date_checked": datetime.date.today().isoformat(), "checked_by": a.checked_by,
           "screenshot": a.screenshot, "verdict": "USABLE_AFTER_RECORD" if action != "ask_it" else "HUMAN_REVIEW",
           "conditions": note}
    new = not os.path.exists(a.log)
    with open(a.log, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RECORD_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    print(json.dumps({"logged": a.log, "row": row}, indent=2))


def main():
    ap = argparse.ArgumentParser(prog="imgrights", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="gather evidence + verdict")
    c.add_argument("paths", nargs="+")
    c.add_argument("--out", help="write JSON report here")
    c.add_argument("--no-ocr", action="store_true")
    c.add_argument("--zone-text", help="(testing/offline) Zone.Identifier text to use instead of reading the file stream")
    c.add_argument("--trace-done", action="store_true", help="reverse-image trail was completed")
    c.add_argument("--license", help="license verified on the ORIGINAL page, e.g. 'CC BY 4.0' or a CC URL")
    c.add_argument("--source-url"); c.add_argument("--author")
    c.add_argument("--people", choices=["none", "yes", "unknown"], default="unknown")
    c.add_argument("--logos", choices=["none", "yes", "unknown"], default="unknown")
    c.set_defaults(fn=cmd_check)
    l = sub.add_parser("license-page", help="extract license/author from a source page")
    g = l.add_mutually_exclusive_group(required=True)
    g.add_argument("--url"); g.add_argument("--html-file")
    l.set_defaults(fn=cmd_license_page)
    p = sub.add_parser("compare", help="perceptual hash distance")
    p.add_argument("a"); p.add_argument("b")
    p.set_defaults(fn=cmd_compare)
    r = sub.add_parser("record", help="append a complete entry to the image log")
    for k in ("file", "used-in", "source-url", "license", "license-url", "checked-by", "screenshot"):
        r.add_argument("--" + k, required=True)
    r.add_argument("--author"); r.add_argument("--log", default="image_log.csv")
    r.set_defaults(fn=cmd_record)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
