#!/bin/bash

# Script to build and push Docker image to GitHub Container Registry (ghcr.io)
# Usage: ./push-to-ghcr.sh YOUR_GITHUB_TOKEN

if [ -z "$1" ]; then
    echo "Error: GitHub token required"
    echo "Usage: ./push-to-ghcr.sh YOUR_GITHUB_TOKEN"
    echo ""
    echo "To create a token:"
    echo "1. Go to https://github.com/settings/tokens"
    echo "2. Generate new token (classic)"
    echo "3. Select 'write:packages' and 'read:packages' scopes"
    exit 1
fi

GITHUB_TOKEN=$1
GITHUB_USERNAME="ahmedtelkodsh"
IMAGE_NAME="scraping-emails"
REGISTRY="ghcr.io"

echo "Logging in to GitHub Container Registry..."
echo $GITHUB_TOKEN | docker login $REGISTRY -u $GITHUB_USERNAME --password-stdin

if [ $? -ne 0 ]; then
    echo "Login failed!"
    exit 1
fi

echo "Building Docker image..."
docker build -t $IMAGE_NAME:latest .

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

echo "Tagging image for GHCR..."
docker tag $IMAGE_NAME:latest $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:latest
docker tag $IMAGE_NAME:latest $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:v1.0.0

echo "Pushing to GitHub Container Registry..."
docker push $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:latest
docker push $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:v1.0.0

echo ""
echo "✅ Successfully pushed to:"
echo "   - $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:latest"
echo "   - $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:v1.0.0"
echo ""
echo "To pull the image:"
echo "   docker pull $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:latest"
