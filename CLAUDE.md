This is a production daily RSS + HTML generator.

Rules:
- Always produce full-file drop-in replacements when modifying files.
- Never omit unrelated code.
- Do not change GitHub Actions workflow structure unless explicitly asked.
- No new runtime dependencies unless explicitly requested.
- Preserve deterministic daily behavior.
- No headless browsers.
- Always keep existing logging unless improving it.
- RSS Feed must unfurl preview on chat and social platforms with Title, Image and Description

The project must never silently skip a day.
