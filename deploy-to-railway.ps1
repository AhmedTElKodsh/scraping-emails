# Railway Deployment Script
# This script helps deploy your Streamlit app to Railway

Write-Host "🚂 Railway Deployment Helper" -ForegroundColor Cyan
Write-Host ""

# Check if Railway CLI is installed
Write-Host "Checking Railway CLI..." -ForegroundColor Yellow
$railwayVersion = railway --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Railway CLI not found. Install it first:" -ForegroundColor Red
    Write-Host "npm install -g @railway/cli" -ForegroundColor White
    exit 1
}
Write-Host "✅ Railway CLI installed: $railwayVersion" -ForegroundColor Green
Write-Host ""

# Link to project
Write-Host "Linking to Railway project..." -ForegroundColor Yellow
Write-Host "Select 'AI-Scrapping' when prompted" -ForegroundColor Cyan
railway link
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to link project" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Deploy
Write-Host "Deploying to Railway..." -ForegroundColor Yellow
railway up
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Deployment failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "✅ Deployment initiated!" -ForegroundColor Green
Write-Host ""
Write-Host "Monitor your deployment:" -ForegroundColor Cyan
Write-Host "  railway logs" -ForegroundColor White
Write-Host ""
Write-Host "Get your app URL:" -ForegroundColor Cyan
Write-Host "  railway domain" -ForegroundColor White
