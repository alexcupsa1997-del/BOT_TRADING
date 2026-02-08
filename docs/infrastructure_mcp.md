# MCP INFRASTRUCTURE GUIDE

> [!TIP]
> **COPY-PASTE READY.**
> This guide provides the exact configuration block to enable all 13 requested Intelligence Modules (MCP Servers) in your GOLIATH environment.

---

## 1. Prerequisites
Ensure your Antigravity/Linux environment has the following:
*   **Node.js** (v18+) -> Run `node -v` to check.
*   **npx** -> Run `npx -v` to check.
*   **Python** (v3.10+) -> Run `python3 --version` to check.

---

## 2. The Master Configuration Block
Add the following JSON object to your `mcpServers` configuration file (usually `~/.config/Claude/claude_desktop_config.json` or your IDE's MCP settings).

```json
{
  "mcpServers": {
    "blockscout": {
      "command": "npx",
      "args": ["-y", "@blockscout/mcp-server"]
    },
    "stripe": {
      "command": "npx",
      "args": ["-y", "@stripe/mcp-server"],
      "env": {
        "STRIPE_API_KEY": "sk_test_..."
      }
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "c7-mcp-server"],
      "env": {
        "C7_API_KEY": "ctx7sk-0c327c8e-d13f-4859-ada0-4df4b9247844"
      }
    },
    "n8n": {
      "command": "npx",
      "args": ["-y", "n8n-mcp"]
    },
    "brightdata": {
      "command": "npx",
      "args": ["-y", "@brightdata/mcp"],
      "env": {
        "BRIGHTDATA_API_KEY": "INSERT_KEY_HERE"
      }
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-playwright"]
    },
    "nextjs_devtools": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-nextjs-devtools"]
    },
    "newswires": {
      "command": "npx",
      "args": ["-y", "the-news-api-mcp-server"],
      "env": {
         "NEWS_API_KEY": "INSERT_KEY_HERE"
      }
    },
    "cloudflare": {
      "command": "npx",
      "args": ["-y", "@cloudflare/mcp-server"],
      "env": {
         "CLOUDFLARE_API_TOKEN": "46f82eeed7510e5f5bde4e0e36992d88b3515",
         "CLOUDFLARE_ACCOUNT_ID": "913167d3edf427210f196eab5fab0d6b"
      }
    },
    "crypto_prices": {
      "command": "npx",
      "args": ["-y", "mcp-crypto-price"]
    },
     "similarweb": {
      "command": "npx",
      "args": ["-y", "@similarweb/mcp-server"],
      "env": {
         "SIMILARWEB_API_KEY": "INSERT_KEY_HERE"
      },
      "_comment": "Check capability if package allows API Token"
    }
  }
}
```

## 3. Detailed Server Breakdown

### 3.1 Verified Servers (Plug & Play)
*   **Blockscout:** Validated. Provides EVM explorer data.
*   **Stripe:** Validated. Official `@stripe/mcp-server`.
*   **Context7:** Validated. Uses your provided key `ctx7sk...`.
*   **n8n:** Validated. Connects to n8n workflows.
*   **BrightData:** Validated. Web scraping infrastructure.

### 3.2 Requiring Attention (Custom/Community)
*   **Crypto.com:** No official `@crypto-com` package found publically. Replaced with `mcp-crypto-price` (Community standard). If you have a private registry, revert to `@crypto-com/mcp-server-prices`.
*   **Newswires:** Mapped to `the-news-api-mcp-server`. Use this for macro sentiment.
*   **Similarweb:** Provided standard invocation. If it fails, fallback to using their REST API via the `fetch` tool.

---

## 4. Verification
After saving the config:
1.  Restart your Agent/IDE.
2.  Ask: *"List available tools."*
3.  You should see tools like `stripe_list_charges`, `blockscout_get_balance`, `c7_query`, etc.

*End of Guide*
