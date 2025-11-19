# Tailwind CSS v4 Setup

This project uses **Tailwind CSS v4** via the `@tailwindcss/postcss` plugin for optimal performance and modern CSS features.

## 🚀 Quick Start

### 1. Install Node.js dependencies
```bash
npm install
```

### 2. Build Tailwind CSS
```bash
npm run build:css
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
│   ├── input.css         # Source file with @import "tailwindcss"
│   └── output.css        # Compiled CSS (auto-generated, gitignored)
├── templates/            # HTML templates (scanned for Tailwind classes)
├── postcss.config.js     # PostCSS configuration (Tailwind v4 plugin)
└── package.json          # Node dependencies
```

**Note:** Tailwind CSS v4 does **not** use `tailwind.config.js` - configuration is done via CSS in `input.css`.

## 🎨 Customization

Tailwind CSS v4 uses **CSS-based configuration** instead of JavaScript config files.

Edit `static/input.css` to customize:
- **Theme variables** - Using `@theme` directive
- **Custom variants** - Using `@custom-variant` (e.g., dark mode)
- **Custom CSS** - Using `@layer` directives
- **Custom animations** - Standard CSS keyframes
- **Dark mode** - Already configured with `@custom-variant dark (&:where(.dark, .dark *))`

Example v4 syntax:
```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

@layer base {
  /* Your custom base styles */
}
```

## ⚡ Performance Benefits

- **~400KB smaller** initial page load (no CDN script)
- **Minified CSS** only includes classes you actually use (tree-shaking)
- **Better caching** - CSS file can be cached with long max-age
- **No render-blocking JS** - pure CSS instead of JavaScript
- **Modern CSS** - Uses native CSS features (nesting, custom properties)
- **Faster builds** - v4 is optimized for speed

## 📦 What Changed from v3 to v4

**Key Breaking Changes:**

1. **No `tailwind.config.js`** - Use CSS-based configuration instead
2. **New import syntax** - `@import "tailwindcss"` instead of `@tailwind` directives
3. **PostCSS plugin** - Uses `@tailwindcss/postcss` instead of standalone CLI
4. **Dark mode** - Configure with `@custom-variant` in CSS, not config file
5. **Nesting required** - Need `postcss-nesting` plugin for proper CSS output

**Migration:**
```css
/* Old v3 syntax */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* New v4 syntax */
@import "tailwindcss";
```

## 🔧 Troubleshooting

**CSS not updating?**
- Make sure `npm run watch:css` is running
- Rebuild with `npm run build:css`
- Check PostCSS output for errors

**Dark mode not working?**
- Verify `@custom-variant dark (&:where(.dark, .dark *))` is in `input.css`
- Ensure `postcss-nesting` plugin is installed and in `postcss.config.js`
- Check that `.dark` class is added to `<html>` element when toggling

**Classes not working?**
- Rebuild with `npm run build:css`
- Verify the class exists in Tailwind v4 docs
- Check browser console for CSS loading errors

**Build fails?**
- Run `npm install` to ensure all dependencies are installed
- Verify `postcss.config.js` has: `@tailwindcss/postcss`, `postcss-nesting`, `autoprefixer`
- Check for syntax errors in `static/input.css`

## 📚 Resources

- [Tailwind CSS v4 Documentation](https://tailwindcss.com/docs)
- [Dark Mode Guide](https://tailwindcss.com/docs/dark-mode)
- [PostCSS Nesting](https://github.com/csstools/postcss-plugins/tree/main/plugins/postcss-nesting)
