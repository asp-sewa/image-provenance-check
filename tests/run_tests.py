"""Self-test: python tests/run_tests.py  (needs Pillow; tesseract optional -> OCR case skipped)"""
import json, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); CLI = os.path.join(HERE, "..", "scripts", "imgrights.py")
fx = tempfile.mkdtemp(); subprocess.run([sys.executable, os.path.join(HERE, "make_fixtures.py"), fx], check=True)
fails = []
def run(*args):
    p = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True)
    try: return p.returncode, json.loads(p.stdout)
    except Exception: return p.returncode, p.stdout + p.stderr
def verdict(name, *extra):
    _, o = run("check", os.path.join(fx, name), *extra); return o["results"][0]["verdict"]
def expect(label, got, want):
    ok = got == want; print(("PASS " if ok else "FAIL ") + label + ("" if ok else "  got=%r want=%r" % (got, want)))
    if not ok: fails.append(label)

expect("stock filename blocks", verdict("gettyimages-2299925682-612x612.jpg", "--no-ocr"), "BLOCK")
if shutil.which("tesseract"): expect("OCR credit blocks", verdict("flood_relief.jpg"), "BLOCK")
expect("metadata creator/copyright blocks w/o license", verdict("meta_owned.jpg", "--no-ocr"), "BLOCK")
expect("clean image is NOT cleared (needs trace)", verdict("clean_unknown.jpg", "--no-ocr"), "TRACE_REQUIRED")
expect("trace done, nothing found -> replace", verdict("clean_unknown.jpg", "--no-ocr", "--trace-done"), "REPLACE")
zs = "[ZoneTransfer]\nZoneId=3\nReferrerUrl=https://www.gettyimages.in/detail/photo/x\nHostUrl=https://media.gettyimages.com/a.jpg"
expect("zone stock domain blocks", verdict("clean_unknown.jpg", "--no-ocr", "--zone-text", zs), "BLOCK")
good = ["--no-ocr", "--source-url", "https://commons.wikimedia.org/wiki/File:X.jpg", "--author", "A. Author"]
expect("CC BY + people unknown -> human review", verdict("clean_unknown.jpg", *good, "--license", "CC BY 4.0"), "HUMAN_REVIEW")
expect("CC BY + no people/logos -> usable", verdict("clean_unknown.jpg", *good, "--license", "CC BY 4.0", "--people", "none", "--logos", "none"), "USABLE_AFTER_RECORD")
expect("CC0 usable w/o author", verdict("clean_unknown.jpg", "--no-ocr", "--source-url", "https://x/y", "--license", "CC0", "--people", "none", "--logos", "none"), "USABLE_AFTER_RECORD")
expect("CC BY-NC denied", verdict("clean_unknown.jpg", *good, "--license", "https://creativecommons.org/licenses/by-nc/4.0/", "--people", "none", "--logos", "none"), "REPLACE")
expect("CC BY-SA -> ask IT", verdict("clean_unknown.jpg", *good, "--license", "CC BY-SA 4.0", "--people", "none", "--logos", "none"), "HUMAN_REVIEW")
expect("unknown license denied", verdict("clean_unknown.jpg", *good, "--license", "free for all lol", "--people", "none", "--logos", "none"), "REPLACE")
expect("stock still blocks even with claimed license", verdict("gettyimages-2299925682-612x612.jpg", *good, "--license", "CC0"), "BLOCK")
expect("metadata claim + CC BY traced -> human review (not usable)", verdict("meta_owned.jpg", *good, "--license", "CC BY 4.0", "--people", "none", "--logos", "none"), "HUMAN_REVIEW")
expect("missing author -> trace required", verdict("clean_unknown.jpg", "--no-ocr", "--source-url", "https://x/y", "--license", "CC BY 4.0", "--people", "none", "--logos", "none"), "TRACE_REQUIRED")
_, c = run("compare", os.path.join(fx, "clean_unknown.jpg"), os.path.join(fx, "clean_unknown_copy.png"))
expect("compare same picture jpg vs png", c["hamming"] <= 10, True)

html = '<html><head><title>Flood</title><meta name="author" content="A. Author"><link rel="license" href="https://creativecommons.org/licenses/by/4.0/"></head></html>'
hp = os.path.join(fx, "p.html"); open(hp, "w").write(html)
_, lp = run("license-page", "--html-file", hp)
expect("license-page finds CC BY + author", (lp["candidates"][0]["license"], lp["page"]["authors"]), ("cc-by", ["A. Author"]))

log = os.path.join(fx, "log.csv"); shot = os.path.join(fx, "s.png"); open(shot, "wb").write(b"x")
rec = ["record", "--file", "a.jpg", "--used-in", "home", "--source-url", "https://x", "--author", "A", "--license", "CC BY 4.0",
       "--license-url", "https://creativecommons.org/licenses/by/4.0/", "--checked-by", "gd", "--log", log]
rc, _ = run(*rec, "--screenshot", os.path.join(fx, "missing.png")); expect("record refuses missing screenshot", rc != 0, True)
rc, _ = run(*rec, "--screenshot", shot); expect("record writes complete entry", rc == 0 and os.path.exists(log), True)
print("\n%d failure(s)" % len(fails)); sys.exit(1 if fails else 0)
