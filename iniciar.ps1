$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$qaPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $qaPython)) { throw 'Ambiente local ausente. Consulte README.md para recuperar o ambiente.' }
try {
    $qaHealth = Invoke-WebRequest -Uri 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 2 -UseBasicParsing
    if ($qaHealth.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8501'; exit 0 }
} catch {}
Start-Process -FilePath $qaPython -ArgumentList '-m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'app.log') -RedirectStandardError (Join-Path $PSScriptRoot 'app-error.log')
for ($qaAttempt = 0; $qaAttempt -lt 30; $qaAttempt++) {
    Start-Sleep -Seconds 1
    try {
        $qaHealth = Invoke-WebRequest -Uri 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 2 -UseBasicParsing
        if ($qaHealth.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8501'; exit 0 }
    } catch {}
}
throw 'Falha ao iniciar QA LSF. Consulte app-error.log.'
