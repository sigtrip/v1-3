#!/usr/bin/env bash
#
# create_release.sh - Create GitHub release v1.3.0
#
# Usage:
#   ./create_release.sh
#

set -e

VERSION="v1.3.0"
RELEASE_NAME="ARGOS Universal OS v1.3 - Security Hardened"
TAG="v1.3.0"

echo "🚀 Creating GitHub Release $VERSION"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub"
    echo "Run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI is ready"
echo ""

# Create release
echo "📝 Creating release..."

gh release create "$TAG" \
    --title "$RELEASE_NAME" \
    --notes-file RELEASE_NOTES_v1.3.md \
    --latest

echo ""
echo "✅ Release $VERSION created successfully!"
echo ""
echo "View release: https://github.com/sigtrip/v1-3/releases/tag/$TAG"
