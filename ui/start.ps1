# Start both the FastAPI backend and the React dev server
# Run this from the repo root: .\ui\start.ps1

$root = Split-Path $PSScriptRoot -Parent

# Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
  cd '$root'
  Write-Host 'Starting FastAPI backend on http://localhost:8000' -ForegroundColor Cyan
  uvicorn ui.backend.main:app --reload --port 8000
"

# Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
  cd '$root\ui\frontend'
  Write-Host 'Starting React dev server on http://localhost:5173' -ForegroundColor Cyan
  npm run dev
"

Write-Host ""
Write-Host "Opening http://localhost:5173 in a few seconds..." -ForegroundColor Green
Start-Sleep 3
Start-Process "http://localhost:5173"
