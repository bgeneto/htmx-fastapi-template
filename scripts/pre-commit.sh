#!/usr/bin/env bash
# Git pre-commit hook to compile translations
# Install: ln -s ../../scripts/pre-commit.sh .git/hooks/pre-commit

set -e

echo "🌐 Compiling translations..."

# Check if translations directory exists
if [ ! -d "translations" ]; then
    echo "⚠️  No translations directory found, skipping..."
    exit 0
fi

# Check if babel is installed
if ! command -v pybabel &> /dev/null; then
    echo "⚠️  Babel not installed, skipping translation compilation"
    echo "   Install with: pip install babel"
    exit 0
fi

# Compile translations
if pybabel compile -d translations 2>&1 | grep -q "compiling catalog"; then
    echo "✓ Translations compiled successfully"

    # Stage the compiled .mo files
    git add translations/*/LC_MESSAGES/*.mo 2>/dev/null || true
else
    echo "⚠️  No translations to compile"
fi

exit 0
