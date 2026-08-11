# Security policy

Do not open a public issue for a vulnerability that could expose local files,
execute untrusted converter output, or leak private library metadata. Contact
the repository maintainer privately through the contact method listed on the
repository profile and include a minimal reproduction without personal PDFs or
credentials.

PaperMason's intended boundary is local file organization. Treat PDF converters
as separate, potentially complex dependencies and keep them updated from their
official sources. Before reporting a converter-specific issue, confirm whether
it reproduces with PaperMason's catalog-only commands (`init`, `bootstrap`,
`search`, or `verify`).
