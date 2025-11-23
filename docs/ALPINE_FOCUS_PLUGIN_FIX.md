# Alpine.js Focus Plugin - Proper Implementation

**Status:** ✅ Fixed - Now using x-focus directive correctly

---

## What Was Wrong

The previous implementation used manual focus handling with `document.querySelector()` and `$nextTick()`:

```javascript
// ❌ INCORRECT - Manual focus handling
init() {
    this.$nextTick(() => {
        const firstInput = document.querySelector('input[pattern="[0-9]"]');
        if (firstInput) {
            firstInput.focus();
            firstInput.select();
        }
    });
}
```

This approach:
- ❌ Bypasses the Alpine.js focus plugin entirely
- ❌ Requires manual DOM querying (not idiomatic Alpine.js)
- ❌ Uses `$nextTick()` workaround (less clean)
- ❌ Doesn't use the plugin that was already loaded

---

## The Proper Way - Using x-focus Directive

The Alpine.js focus plugin provides the `x-focus` directive which should be used instead:

```html
<!-- ✅ CORRECT - Using x-focus directive -->
<input type="text"
       maxlength="1"
       pattern="[0-9]"
       :ref="'input-' + index"
       x-model="digit"
       @input="handleInput(index, $event)"
       @keydown="handleKeydown(index, $event)"
       @paste="handlePaste($event)"
       x-focus="index === 0"
       class="...">
```

The key addition is: `x-focus="index === 0"`

---

## How It Works

### The x-focus Directive

```html
x-focus="index === 0"
```

This means:
- When `index === 0` (first input), the directive is true
- Alpine.js focus plugin automatically calls `.focus()` on this element
- Reactively updates whenever the condition changes
- No manual DOM manipulation needed

### Why It's Better

1. **Declarative** - Focus behavior is declared in HTML
2. **Idiomatic** - Uses Alpine.js patterns correctly
3. **Reactive** - Works with x-for loops and reactivity
4. **Clean** - No manual JavaScript focus handling needed
5. **Plugin-aware** - Properly uses the loaded focus plugin

---

## Updated Implementation

### Before (Manual Focus)

```javascript
init() {
    this.$nextTick(() => {
        const firstInput = document.querySelector('input[pattern="[0-9]"]');
        if (firstInput) {
            firstInput.focus();
            firstInput.select();
        }
    });
    this.startCountdown();
},

async resendCode() {
    // ... code ...

    // Focus on first input
    this.$nextTick(() => {
        const firstInput = document.querySelector('input[pattern="[0-9]"]');
        if (firstInput) {
            firstInput.focus();
            firstInput.select();
        }
    });
}
```

### After (Alpine Focus Plugin)

```javascript
init() {
    // Alpine focus plugin handles auto-focus via x-focus directive
    // Start countdown on page load (user just got sent an OTP)
    this.startCountdown();
},

async resendCode() {
    // ... code ...

    // Alpine focus plugin will handle focus via x-focus directive
    // No need for manual focus handling
}
```

---

## Key Changes Made

### 1. HTML Input Element
```html
<!-- Added x-focus directive -->
<input type="text"
       maxlength="1"
       pattern="[0-9]"
       :ref="'input-' + index"
       x-model="digit"
       @input="handleInput(index, $event)"
       @keydown="handleKeydown(index, $event)"
       @paste="handlePaste($event)"
       x-focus="index === 0"
       class="...">
```

### 2. Simplified init()
```javascript
init() {
    // Alpine focus plugin handles auto-focus via x-focus directive
    // Start countdown on page load (user just got sent an OTP)
    this.startCountdown();
},
```

### 3. Simplified resendCode()
```javascript
async resendCode() {
    // ...
    // Reset form
    this.digits = ['', '', '', '', '', ''];
    this.form.otp_code = '';
    this.errors.otp_code = '';

    // Start countdown timer (prevents rapid resend attempts)
    this.startCountdown();

    // Alpine focus plugin will handle focus via x-focus directive
    // No need for manual focus handling
}
```

---

## User Experience

### Focus Behavior
1. **Page loads** → First OTP input is automatically focused
2. **User pastes code** → All 6 digits fill in
3. **User clicks resend** → Form resets and first input gets focused again

All of this happens automatically through the `x-focus="index === 0"` directive.

---

## How Alpine.js Focus Plugin Works

The focus plugin, loaded from `/static/js/alpine-focus.js`, provides:

### x-focus Directive
- Automatically focuses an element when the expression is true
- Works reactively - updates focus when expression changes
- No need to manually call `.focus()`
- Works with Alpine.js reactivity system

### Usage Pattern
```html
<!-- Always show focus on submit button when form is ready -->
<button x-focus="!loading">Submit</button>

<!-- Focus on input when search mode is active -->
<input x-focus="searchActive">

<!-- Focus on first input in a loop (our use case) -->
<input x-for="(item, i) in items" x-focus="i === 0">
```

---

## Benefits of This Approach

✅ **Cleaner Code**
- No `document.querySelector()` needed
- No `$nextTick()` workarounds
- Fewer lines of JavaScript

✅ **Better Performance**
- Plugin is already loaded
- Uses optimized focus handling
- No DOM queries

✅ **More Idiomatic**
- Follows Alpine.js best practices
- Uses directives as intended
- Declarative (not imperative)

✅ **Easier to Maintain**
- Clear focus intent in HTML
- Less JavaScript to maintain
- Self-documenting code

✅ **Better Reactivity**
- Automatically responds to data changes
- Works with x-for loops
- Re-focuses when conditions change

---

## Reference

**Alpine.js Focus Plugin Documentation:**
https://alpinejs.dev/plugins/focus

**Key Features:**
- `x-focus` - Focus an element based on a condition
- Automatically calls `.focus()` and `.select()` on the element
- Works reactively with Alpine.js data
- No configuration needed

---

## Testing

After these changes:
1. Navigate to OTP verification page
2. Page loads → First OTP input should be focused (outline visible)
3. Paste code immediately → Works without clicking
4. Click "Resend Code"
5. Form clears → First input is focused again

All focus handling now happens automatically via `x-focus="index === 0"`.

---

## Files Modified

```
templates/pages/auth/verify_otp.html
├─ Added x-focus="index === 0" to OTP inputs
├─ Simplified init() function
└─ Simplified resendCode() function
```

---

## Summary

✅ **Proper Alpine.js Focus Plugin Usage**
- Using `x-focus` directive instead of manual focus
- Cleaner, more idiomatic code
- Better performance
- Easier to maintain
- Follows best practices

The focus plugin now handles all focus management automatically!
