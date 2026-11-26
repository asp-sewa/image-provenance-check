$src = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($d in @("$HOME\.claude\skills", "$HOME\.agents\skills", "$HOME\.gemini\skills")) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  $t = Join-Path $d "image-provenance-check"
  if (Test-Path $t) { Remove-Item -Recurse -Force $t }
  Copy-Item -Recurse $src $t
  Write-Host "installed -> $t"
}
python -c "import PIL" 2>$null; if ($LASTEXITCODE -ne 0) { Write-Host "NOTE: pip install pillow" }
