import js from "@eslint/js"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import tseslint from "typescript-eslint"
import eslintConfigPrettier from "eslint-config-prettier"
import { defineConfig, globalIgnores } from "eslint/config"

export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      eslintConfigPrettier,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // FE_Implementation.md §6.4 — keep raw colour out of the codebase now
      // that the token layer exists. A one-time grep would have decayed by
      // Phase 6; this feeds pnpm lint:frontend -> check:fe -> check, which the
      // pre-push hook and CI both already run.
      //
      // Three selectors, because raw colour arrives three different ways:
      //   1. a Tailwind arbitrary value    bg-[#111]
      //   2. a Tailwind palette colour     text-emerald-500
      //   3. a bare literal in a prop      stroke="#ffffff"
      // The third is the one a utility-class lint cannot see and is exactly
      // where the 39 chart-layer colours were hiding.
      //
      // Deliberately matched on Literal only, never TemplateLiteral: the
      // Accident Frequency by Location ramp is a computed hsl() that §2.2
      // keeps, and a computed ramp is not a hardcoded colour.
      "no-restricted-syntax": [
        "error",
        {
          selector: "Literal[value=/(^|\\s)[a-zA-Z-]*-\\[(#|rgb|hsl|color-mix)[^\\]]*\\]/]",
          message:
            "Arbitrary colour value. Use a design token from index.css (FE_Implementation.md §2) — bg-surface-1, text-fg-muted, border-stroke, etc.",
        },
        {
          selector:
            "Literal[value=/(^|\\s)(text|bg|border|from|via|to|ring|fill|stroke|divide|outline|placeholder|shadow|accent|caret)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-[0-9]{2,3}(\\/[0-9]+)?(\\s|$)/]",
          message:
            "Tailwind palette colour. Use a semantic token — text-success, text-warning, text-danger and their -subtle / -border variants.",
        },
        {
          selector:
            "Literal[value=/^\\s*(#[0-9a-fA-F]{3,8}|rgba?\\([^)]*\\)|hsla?\\([^)]*\\))\\s*$/]",
          message:
            "Bare colour literal. Chart and inline-style colours go through var(--color-*) — see §2.2's chart tokens.",
        },
      ],
    },
  },
])
