# PowerShell script to build and push Docker image to GitHub Container Registry (ghcr.io)
# Usage: .\push-to-ghcr.ps1 YOUR_GITHUB_TOKEN

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubToken
)

$GITHUB_USERNAME = "ahmedtelkodsh"
$IMAGE_NAME = "scraping-emails"
$REGISTRY = "ghcr.io"

Write-Host "Logging in to GitHub Container Registry..." -ForegroundColor Cyan
$GitHubToken | docker login $REGISTRY -u $GITHUB_USERNAME --password-stdin

if ($LASTEXITCODE -ne 0) {
    Write-Host "Login failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`nBuilding Docker image..." -ForegroundColor Cyan
docker build -t "${IMAGE_NAME}:latest" .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`nTagging image for GHCR..." -ForegroundColor Cyan
docker tag "${IMAGE_NAME}:latest" "${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:latest"
docker tag "${IMAGE_NAME}:latest" "${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:v1.0.0"

Write-Host "`nPushing to GitHub Container Registry..." -ForegroundColor Cyan
docker push "${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:latest"
docker push "${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:v1.0.0"

Write-Host "`n✅ Successfully pushed to:" -ForegroundColor Green
Write-Host "   - ${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:latest" -ForegroundColor Green
Write-Host "   - ${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:v1.0.0" -ForegroundColor Green
Write-Host "`nTo pull the image:" -ForegroundColor Yellow
Write-Host "   docker pull ${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:latest" -ForegroundColor Yellow
