# Tailwind CSS Setup

This project now uses **self-hosted Tailwind CSS** instead of the CDN for better performance.

## 🚀 Quick Start

### 1. Install Node.js dependencies
```bash
npm install
```

### 2. Build Tailwind CSS
```bash
npm run build:css
```

Or use the setup script:
```bash
./setup-tailwind.sh
```

## 📝 Available Commands

| Command             | Description                                     |
| ------------------- | ----------------------------------------------- |
| `npm run build:css` | Build minified production CSS (one-time)        |
| `npm run watch:css` | Watch for changes and rebuild CSS automatically |
| `npm run dev`       | Alias for `watch:css`                           |

## 🛠️ Development Workflow

**For development**, run in a separate terminal:
```bash
npm run watch:css
```

This will watch your templates and automatically rebuild `static/output.css` when you make changes.

**For production**, build once:
```bash
npm run build:css
```

## 📁 File Structure

```
├── static/
│   ├── input.css         # Source file with Tailwind directives
│   └── output.css        # Compiled CSS (auto-generated, gitignored)
├── templates/            # HTML templates (scanned for classes)
├── tailwind.config.js    # Tailwind configuration
├── postcss.config.js     # PostCSS configuration
└── package.json          # Node dependencies
```

## 🎨 Customization

Edit `tailwind.config.js` to customize:
- Colors
- Fonts
- Breakpoints
- Plugins
- Content paths (files to scan for classes)

Edit `static/input.css` to add:
- Custom CSS
- Additional @layer directives
- Custom animations

## ⚡ Performance Benefits

- **~400KB smaller** initial page load (no CDN script)
- **Minified CSS** only includes classes you actually use
- **Better caching** - CSS file can be cached with long max-age
- **No render-blocking JS** - pure CSS instead of JavaScript
- **Tree-shaking** - unused Tailwind classes are removed

## 📦 What Changed

**Before** (CDN):
```html
<script src="https://cdn.tailwindcss.com"></script>
```

**After** (Self-hosted):
```html
<link rel="stylesheet" href="/static/output.css">
```

## 🔧 Troubleshooting

**CSS not updating?**
- Make sure `npm run watch:css` is running
- Check that your HTML files are in the `content` paths in `tailwind.config.js`

**Classes not working?**
- Rebuild with `npm run build:css`
- Verify the class exists in Tailwind (check docs)

**Build fails?**
- Run `npm install` to ensure dependencies are installed
- Check for syntax errors in `tailwind.config.js`
