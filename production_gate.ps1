Write-Host "============================================================"
Write-Host "ATLAS PRODUCTION PRE-COMMIT GATE"
Write-Host "============================================================"

Write-Host "`n[1] GIT DIFF CHECK"
git diff --check
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: whitespace/diff error"
    exit 1
}
Write-Host "PASS"

Write-Host "`n[2] PYTHON COMPILE CHECK"
.\.venv\Scripts\python.exe -m compileall -q ai core stock_intelligence tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: Python compile error"
    exit 1
}
Write-Host "PASS"

Write-Host "`n[3] FULL PYTEST"
.\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: pytest"
    exit 1
}
Write-Host "PASS"

Write-Host "`n[4] TTM INTEGRATION GATE"
.\.venv\Scripts\python.exe integration_gate.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: TTM integration"
    exit 1
}
Write-Host "PASS"

Write-Host "`n[5] FINAL DIFF STAT"
git diff --stat

Write-Host "`n============================================================"
Write-Host "ALL PRODUCTION GATES PASSED"
Write-Host "============================================================"
