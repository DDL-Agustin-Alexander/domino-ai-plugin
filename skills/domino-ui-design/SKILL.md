---
name: domino-ui-design
description: Build Domino-styled web application UIs that match the Domino Design System, and review existing Domino app UIs against Domino's UX rules. The build recipe is FastAPI serving an HTML page that loads React 18 and Ant Design 5 from a CDN (no build step) with Domino theme tokens (colors, typography, spacing), Highcharts styling, proxy-safe relative routing and Domino API authentication; the same tokens are mapped for Streamlit and Dash. Use when the user asks for a "Domino app", "Domino UI", "Domino dashboard" or "Domino design system" look, wants UI components, UX writing, error, empty-state, form or table patterns for a Domino app, or asks for a UX review of a Domino app screenshot. For a Vite + React SPA on the official component library use domino-ui-bootstrap instead.
compatibility: Domino 6.3 and Domino Cloud. Requires DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token.
---

# Domino UI Design System

Applies to Domino 6.3 and Domino Cloud.

## Architecture

The build recipe is **FastAPI** (Python backend, served by uvicorn on `0.0.0.0:8888`) plus **Ant Design 5** loaded from a CDN and driven with `React.createElement`, so there is no build step. Keep CSS and JS in static files referenced with relative paths (Domino serves the App under a proxy prefix). Log errors to stdout so they land in the App logs. For Streamlit or Dash, apply the same tokens as described under "Other frameworks".

### CDN setup

Include in the HTML `<head>`. React 19 ships no UMD build, so the no-build approach stays on React 18 with Ant Design 5; `antd.min.js` expects `react`, `react-dom` and `dayjs` to be loaded before it.

```html
<script src="https://unpkg.com/react@18.3.1/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/dayjs@1.11.23/dayjs.min.js"></script>
<script src="https://unpkg.com/antd@5.29.3/dist/antd.min.js"></script>
<link href="https://unpkg.com/antd@5.29.3/dist/reset.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://code.highcharts.com/highcharts.js"></script>
```

If the deployment blocks external CDNs or fonts, vendor the files under `static/` or ask an admin to allowlist them (https://docs.domino.ai/cloud/platform-capabilities/features/apps/authentication-and-identity/whitelist-resources). Highcharts is loaded unpinned from its own CDN and needs a commercial licence for business use; pin a version and confirm the licence before shipping.

```javascript
const { ConfigProvider, Button, Table, Modal, Select, Input, Form, Space, Card, Tag, Alert } = antd;
const { createElement: h, useState, useEffect } = React;
```

## Domino theme

Wrap the app in `ConfigProvider` with this theme:

```javascript
const dominoTheme = {
  token: {
    colorPrimary: '#543FDE',          // Purple
    colorPrimaryHover: '#3B23D1',
    colorPrimaryActive: '#311EAE',
    colorText: '#2E2E38',
    colorTextSecondary: '#65657B',
    colorTextTertiary: '#8F8FA3',
    colorSuccess: '#28A464',
    colorWarning: '#CCB718',
    colorError: '#C20A29',
    colorInfo: '#0070CC',
    colorBgContainer: '#FFFFFF',
    colorBgLayout: '#FAFAFA',
    colorBorder: '#E0E0E0',
    fontFamily: 'Inter, Lato, Helvetica Neue, Helvetica, Arial, sans-serif',
    fontSize: 14,
    borderRadius: 4,
    borderRadiusLG: 8,
  },
  components: {
    Button: { primaryShadow: 'none', defaultShadow: 'none' },
    Table: { headerBg: '#FAFAFA', rowHoverBg: '#F5F5F5' },
  },
};
```

### Top navigation bar

Height 44px, background `#2E2E38`, text `#FFFFFF`. Use the Domino logo at height 32px. Primary actions on the right. Only add nav items with real destinations.

**Domino logo:** `assets/domino-logo.svg`, resolved relative to this skill's directory. White text on a transparent background, designed for the dark nav bar.

### Charts (Highcharts)

```javascript
Highcharts.setOptions({
  colors: ['#543FDE', '#0070CC', '#28A464', '#CCB718', '#FF6543', '#E835A7', '#2EDCC4', '#A9734C'],
  chart: { style: { fontFamily: 'Inter, Lato, Helvetica Neue, Arial, sans-serif' } },
});
```

## Domino API integration

Call Domino APIs from the FastAPI backend, never from browser JavaScript. In a run use `DOMINO_API_PROXY` with no header, or a short-lived bearer from `http://localhost:8899/access-token` on `$DOMINO_API_HOST`; outside a run a Personal Access Token or service account token. Legacy API keys are deprecated. Public API routes live under `/api/...` (verify them in the published specs); `/v4/...` is the Domino Internal API and may change between versions. Helper code, base-path table, governance base URL and verification sources: [references/api-integration.md](references/api-integration.md). When an API call fails, show the error and name the missing variable or permission; do not fabricate data.

## Running the App

```bash
#!/bin/bash
# app.sh
set -e
uvicorn app:app --host 0.0.0.0 --port 8888
```

Domino requires `0.0.0.0:8888`. Reference static files and API routes relatively (`static/app.js`, `fetch("api/jobs")`), never `/static/...` or `/api/...`: the proxy strips the App's prefix before forwarding. Full layout, Streamlit and Dash configs and troubleshooting: `domino-apps` skill (FRAMEWORKS.md).

## Other frameworks

- **Streamlit**: add the tokens to the `config.toml` that `app.sh` writes: `[theme] primaryColor = "#543FDE"`, `backgroundColor = "#FFFFFF"`, `secondaryBackgroundColor = "#FAFAFA"`, `textColor = "#2E2E38"`, `font = "sans-serif"`.
- **Dash**: Dash serves `assets/*.css` automatically; define the tokens as CSS custom properties there (`--domino-primary: #543FDE;`) and set `font-family: Inter, Lato, "Helvetica Neue", Helvetica, Arial, sans-serif` on `body`.
- The UX rules below apply to every framework.

## UX design rules

For detailed UX principles, writing guidelines, component patterns, and review checklists, read [references/ux-design-rules.md](references/ux-design-rules.md).

Key rules to always follow:
- **Empty states must be actionable**: answer what is this, why is it empty, what can I do.
- **Error messages must be human-readable** with guidance on what to do next.
- **Disabled elements must explain why** they are disabled (tooltip).
- **Truncated table text must have tooltips.**
- **Icon-only buttons must have tooltips.**
- **Use sentence case** for UI text (not Title Case).
- **No exclamation points** in UI copy.
- **Side panels should overlay**, not push or crush main content.
- **Checkboxes use positive framing**: checked = on or enabled, never checked = off.

## UX review

When reviewing a Domino app UI, read [references/ux-design-rules.md](references/ux-design-rules.md) and check against the review checklists. Classify issues as High, Medium or Low severity.

## Documentation reference

Specs: https://docs.domino.ai/api-specs/cloud/public-api.json and https://docs.domino.ai/api-specs/6.3/public-api.json . Apps docs: https://docs.domino.ai/cloud/platform-capabilities/features/apps . Verification sources and the deployment's own `/docs` reference: [references/api-integration.md](references/api-integration.md).
