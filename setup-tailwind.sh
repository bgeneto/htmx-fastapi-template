#!/bin/bash

# Install npm dependencies
echo "📦 Installing npm dependencies..."
npm install

# Build Tailwind CSS
echo "🎨 Building Tailwind CSS..."
npm run build:css

echo "✅ Setup complete! Tailwind CSS compiled to static/css/output.css"
echo ""
echo "Development commands:"
echo "  npm run watch:css  - Watch for changes and rebuild CSS"
echo "  npm run build:css  - Build minified production CSS"
