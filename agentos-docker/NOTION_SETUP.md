# Notion Integration Setup

How to connect your Notion workspace so the app can read pages via the API.

---

## 1. Create a Notion Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **+ New integration**
3. Give it a name (e.g. `sweetspot-discovery`)
4. Set **Associated workspace** to the workspace that holds your discovery pages
5. Under **Capabilities**, enable:
   - Read content ✓
   - *(leave Update/Insert off unless needed)*
6. Click **Save** → copy the **Internal Integration Token** (`ntn_...`)

---

## 2. Store the Token

Add it to `.env` in the project root (never commit this file):

```
NOTION_TOKEN=ntn_your_token_here
NOTION_SAFE_MODE=false
```

`.env` is already in `.gitignore`.

---

## 3. Share Pages with the Integration

This is the step people most often miss. Notion requires you to explicitly grant access page by page (or via a parent page to cover all children).

**For each top-level page you want the app to read:**

1. Open the page in Notion
2. Click **···** (top-right menu)
3. Click **Connections**
4. Find your integration name → click **Confirm**

> **Tip:** Share a top-level workspace page once and all child pages inherit access automatically.

To verify access from the terminal:

```bash
curl -s "https://api.notion.com/v1/pages/<PAGE_ID>" \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" | python3 -c "
import sys, json; d=json.load(sys.stdin)
print('✅ Accessible' if d.get('object')=='page' else '❌ ' + d.get('message',''))
"
```

---

## 4. Customer Config Page

Each customer can have a dedicated Notion config page that controls the output structure.
Create a page with this format and share it with the integration:

```
# <Customer Name>

## Required Sections
- Executive Summary
- Key Findings
- Recommendations
- <add or remove sections as needed>

## Terminology
- OldTerm → NewTerm
- CRM → Customer Data Platform

## Slide Budget
- Min slides: 8
- Max slides: 25
- Max per section: 3
```

Paste the URL into the **Customer config URL** field in the Streamlit UI.

---

## 5. What the App Can and Cannot Read

| Content type | Supported |
|---|---|
| Text paragraphs | ✅ |
| Headings (H1/H2/H3) | ✅ |
| Bullet and numbered lists | ✅ |
| Toggles (and their children) | ✅ |
| Callouts | ✅ |
| Code blocks | ✅ |
| Sub-pages (recursive, up to 3 levels deep) | ✅ |
| Notion tables | ❌ (not yet) |
| Embedded databases | ❌ (not yet) |
| Images / PDFs | ❌ |
| Pages in another workspace | ❌ (separate token needed) |

---

## 6. Multiple Workspaces

If your discovery pages live in a different workspace from your config pages, you need a separate integration token per workspace. Currently the app uses one `NOTION_TOKEN`. Multi-workspace support is a planned extension.
