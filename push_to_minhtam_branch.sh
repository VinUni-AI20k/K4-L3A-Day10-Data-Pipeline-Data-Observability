#!/bin/bash
# Push to MinhTam branch on GitHub

cd "$(dirname "$0")"

echo "=== Pushing to MinhTam branch ==="

# Set git identity
git config user.name "Minh Tam"
git config user.email "MinhTam@example.com"

# Remove any stale locks
rm -f .git/*.lock .git/refs/heads/*.lock 2>/dev/null

# Create or switch to MinhTam branch
git checkout -b MinhTam 2>/dev/null || git checkout MinhTam

# Stage all changes
git add .

# Commit
git commit -m "feat: complete Day 10 data observability pipeline - corruption flow, quality checks, and repair"

# Push to remote
git push -u origin MinhTam

echo ""
echo "=== Done! ==="
echo "Branch pushed to: https://github.com/SxAinsworth/K4-L3A-Day10-TruongGiang/tree/MinhTam"
