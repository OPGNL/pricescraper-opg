---
name: config-steps-extraction
description: Creates step-by-step scrapper configuration to input product height/length, width, thickness (optional) and extracts price from a product url
---

# Config Steps Extraction

This skill helps you create scraper configurations for new domain websites. It analyzes a product page and generates a JSON configuration that defines the step-by-step process to input dimensions and extract pricing information.

## Instructions

When a user provides a product URL and asks to create a scraper configuration, follow these steps:

### 1. Analyze the Product Page
- Use the `WebFetch` tool to visit the product URL
- Identify and document the CSS selectors for:
  - **Width input field** (Largeur, Width, Breite, etc.)
  - **Height/Length input field** (Hauteur, Length, Länge, Höhe, etc.)
  - **Thickness selector** (optional - dropdown or radio buttons)
  - **Quantity input field**
  - **Price display element** (including whether it includes VAT)
  - **Add to cart button**
  - **Cookie consent buttons** (if present)
  - **Cart/Checkout navigation elements**
  - **Any configuration steps** that must be completed before inputs appear

### 2. Review Sample Configurations
- Read `sample_configurations.json` to understand the standard structure
- Look for similar websites (same platform, similar workflow) to use as templates
- Note common patterns like PrestaShop, WooCommerce, custom configurators

### 3. Create the Configuration Structure

Generate a JSON object following this structure:

```json
{
  "domain": "example.com",
  "config": {
    "categories": {
      "shipping": {
        "steps": [
          // Steps to calculate shipping cost
        ]
      },
      "square_meter_price": {
        "steps": [
          // Steps to calculate per-square-meter price
        ]
      }
    },
    "domain": "example.com"
  },
  "created_at": "YYYY-MM-DDTHH:MM:SS",
  "updated_at": null
}
```

### 4. Define Configuration Steps

Use these step types based on the page requirements:

#### Click Steps
```json
{
  "type": "click",
  "selector": "#cookie-accept-button",
  "description": "Accept cookies",
  "continue_on_error": true
}
```

#### Wait Steps
```json
{
  "type": "wait",
  "duration": "short"  // Options: "short", "default", "long", "longest"
}
```

#### Input Steps (for dimensions)
```json
{
  "type": "input",
  "selector": "#width-input",
  "value": "{width}",
  "unit": "mm",  // or "cm" depending on website
  "clear_first": true
}
```

**Available dimension variables:**
- `{width}` - Width in millimeters (system converts to target unit)
- `{length}` or `{height}` - Length/height in millimeters
- `{thickness}` - Thickness in millimeters
- `{quantity}` - Number of pieces

#### Select Steps (for dropdowns/thickness)
```json
{
  "type": "select",
  "selector": "select.thickness-dropdown",
  "value": "{thickness}",
  "unit": "mm",
  "continue_on_error": true
}
```

#### Read Price Steps
```json
{
  "type": "read_price",
  "selector": ".product-price",
  "includes_vat": false,  // true if price includes VAT
  "calculation": "price / {quantity}",  // optional: for per-unit calculations
  "continue_on_error": false
}
```

#### Blur Steps (trigger calculations)
```json
{
  "type": "blur"
}
```

#### Modify Steps (custom JavaScript execution)
```json
{
  "type": "modify",
  "selector": "#custom-element",
  "script": "element.value = '100'; element.dispatchEvent(new Event('input', { bubbles: true }));",
  "description": "Set custom value and trigger input event",
  "continue_on_error": false
}
```

**Use cases for `modify` steps:**
- Manipulate DOM elements that can't be controlled through standard `input`/`click` steps
- Trigger custom events or functions (e.g., `dispatchEvent`, custom framework handlers)
- Set properties or attributes directly on elements
- Bypass UI restrictions or validations for testing
- Execute site-specific JavaScript to trigger calculations or workflows

**Available in script context:**
- `element` - The DOM element matched by the selector
- `{width}`, `{length}`, `{thickness}`, `{quantity}` - Dimension variables (can be used in script strings)

**Common patterns:**
```javascript
// Set value and trigger change event
element.value = '{width}'; element.dispatchEvent(new Event('change', { bubbles: true }));

// Click element programmatically
element.click();

// Remove disabled attribute
element.removeAttribute('disabled');

// Trigger custom framework event (e.g., React)
const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
nativeInputValueSetter.call(element, '{length}');
element.dispatchEvent(new Event('input', { bubbles: true }));
```

### 5. Common Workflow Patterns

#### Pattern A: Simple Product Page
1. Accept cookies (if needed)
2. Input width
3. Wait
4. Input height
5. Blur (trigger price calculation)
6. Wait
7. Read price

#### Pattern B: Add to Cart + Checkout
1. Accept cookies
2. Configure dimensions
3. Set quantity
4. Add to cart
5. Navigate to cart
6. Proceed to checkout
7. Read shipping price

#### Pattern C: Multi-Step Configurator
1. Accept cookies
2. Click configuration step/tab
3. Select shape (rectangle, circle, etc.)
4. Wait for form to load
5. Input dimensions
6. Trigger calculations (blur/click)
7. Read price

### 6. Important Considerations

- **Units**: Always specify the correct unit (`mm` or `cm`). The system handles conversion automatically.
- **VAT**: Set `includes_vat` correctly based on the price display (HT = false, TTC = true)
- **Waits**: Add appropriate wait durations after inputs and clicks to allow for AJAX updates
- **Error Handling**: Use `continue_on_error: true` for optional steps (like cookie consent)
- **Clear First**: Use `clear_first: true` for input fields that may have default values
- **Selectors**: Prefer IDs over classes, and classes over complex CSS paths

### 7. Testing Considerations

After creating the configuration, note any potential issues:
- Dynamic content loading (may need longer waits)
- Multi-step forms (may need intermediate clicks)
- CAPTCHA or anti-bot measures
- Custom JavaScript configurators
- Session/cookie requirements

## Examples

### Example 1: Basic Product Page

**User Request:**
> Create a scraper config for https://example.com/products/acrylic-sheet.html

**Your Response:**

1. First, analyze the page:
   - Use WebFetch to identify selectors
   - Document the workflow

2. Then create the configuration:

```json
{
  "domain": "example.com",
  "config": {
    "categories": {
      "square_meter_price": {
        "steps": [
          {
            "type": "click",
            "selector": "#accept-cookies",
            "continue_on_error": true
          },
          {
            "type": "wait",
            "duration": "short"
          },
          {
            "type": "input",
            "selector": "#product-width",
            "value": "{width}",
            "unit": "cm",
            "clear_first": true
          },
          {
            "type": "wait",
            "duration": "short"
          },
          {
            "type": "input",
            "selector": "#product-height",
            "value": "{length}",
            "unit": "cm",
            "clear_first": true
          },
          {
            "type": "blur"
          },
          {
            "type": "wait",
            "duration": "default"
          },
          {
            "type": "read_price",
            "selector": ".product-price",
            "includes_vat": true
          }
        ]
      }
    },
    "domain": "example.com"
  },
  "created_at": "2026-01-21T00:00:00",
  "updated_at": null
}
```

### Example 2: Multi-Step Configurator

**User Request:**
> Create config for https://plastic-shop.de/custom-sheets with thickness selection

**Your Response:**

```json
{
  "domain": "plastic-shop.de",
  "config": {
    "categories": {
      "square_meter_price": {
        "steps": [
          {
            "type": "click",
            "selector": ".cookie-consent-accept",
            "continue_on_error": true
          },
          {
            "type": "wait",
            "duration": "short"
          },
          {
            "type": "select",
            "selector": "#thickness-select",
            "value": "{thickness}",
            "unit": "mm"
          },
          {
            "type": "wait",
            "duration": "default"
          },
          {
            "type": "click",
            "selector": "#configure-dimensions-tab"
          },
          {
            "type": "wait",
            "duration": "short"
          },
          {
            "type": "input",
            "selector": "#custom-width",
            "value": "{width}",
            "unit": "mm",
            "clear_first": true
          },
          {
            "type": "wait",
            "duration": "short"
          },
          {
            "type": "input",
            "selector": "#custom-height",
            "value": "{length}",
            "unit": "mm",
            "clear_first": true
          },
          {
            "type": "blur"
          },
          {
            "type": "wait",
            "duration": "long"
          },
          {
            "type": "read_price",
            "selector": ".calculated-price",
            "includes_vat": false
          }
        ]
      },
      "shipping": {
        "steps": [
          {
            "type": "click",
            "selector": ".cookie-consent-accept",
            "continue_on_error": true
          },
          {
            "type": "wait",
            "duration": "short"
          },
          {
            "type": "select",
            "selector": "#thickness-select",
            "value": "{thickness}",
            "unit": "mm"
          },
          {
            "type": "wait",
            "duration": "default"
          },
          {
            "type": "input",
            "selector": "#custom-width",
            "value": "{width}",
            "unit": "mm",
            "clear_first": true
          },
          {
            "type": "wait",
            "duration": "short"
          },
          {
            "type": "input",
            "selector": "#custom-height",
            "value": "{length}",
            "unit": "mm",
            "clear_first": true
          },
          {
            "type": "wait",
            "duration": "short"
          },
          {
            "type": "input",
            "selector": "#quantity",
            "value": "{quantity}",
            "unit": "",
            "clear_first": true
          },
          {
            "type": "click",
            "selector": ".add-to-cart-btn"
          },
          {
            "type": "wait",
            "duration": "default"
          },
          {
            "type": "click",
            "selector": ".view-cart-btn"
          },
          {
            "type": "wait",
            "duration": "default"
          },
          {
            "type": "click",
            "selector": ".checkout-btn"
          },
          {
            "type": "wait",
            "duration": "long"
          },
          {
            "type": "read_price",
            "selector": ".shipping-cost",
            "includes_vat": false
          }
        ]
      }
    },
    "domain": "plastic-shop.de"
  },
  "created_at": "2026-01-21T00:00:00",
  "updated_at": null
}
```

## Key Step Type Reference

| Step Type | Purpose | Common Parameters |
|-----------|---------|-------------------|
| `click` | Click DOM elements | `selector`, `description`, `continue_on_error` |
| `input` | Fill form fields | `selector`, `value`, `unit`, `clear_first` |
| `select` | Choose dropdown options | `selector`, `value`, `unit`, `option_index` |
| `wait` | Pause execution | `duration` (short/default/long/longest) |
| `read_price` | Extract price | `selector`, `includes_vat`, `calculation` |
| `blur` | Trigger calculations | None (triggers on last focused element) |
| `modify` | Execute custom JavaScript | `selector`, `script`, `description`, `continue_on_error` |
| `navigate` | Go to URL | `url`, `wait_for_load` |
| `decide_config` | Conditional routing | `selector`, `fallback_config`, `timeout` |

## Common Selector Patterns

- **PrestaShop**: `#quantity_wanted`, `.product-price`, `.add-to-cart`
- **WooCommerce**: `.qty`, `.single_add_to_cart_button`, `.woocommerce-Price-amount`
- **Custom Configurators**: Often use IDs like `#custom_width`, `#custom_height`
- **Cookie Consent**: `.cookie-accept`, `#CybotCookiebotDialogBodyButtonAccept`

## Notes

- Always provide clear, accurate selectors
- Test configurations with various dimension combinations
- Document any limitations or special requirements
- Consider both desktop and mobile layouts if applicable
- Note any anti-scraping measures that may affect reliability
