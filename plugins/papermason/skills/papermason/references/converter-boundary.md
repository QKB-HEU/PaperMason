# Converter boundary

PaperMason owns cataloging and safe local organization. A converter owns PDF
understanding. Keep that boundary explicit so the core library remains useful
without a GPU, network service, or a particular parser.

## Required converter behavior

The converter command receives two placeholders:

```text
{pdf}     absolute source-PDF path
{output}  empty temporary output directory
```

It must finish successfully and create exactly one non-hidden Markdown file
somewhere under `{output}`. Images referenced as `images/foo.png` or
`./images/foo.png` must exist relative to that Markdown file. PaperMason moves
the validated output into `assets/<paper-id>/` and rewrites those local links
to remain valid from `markdown/<paper-id>.md`.

## Failure handling

- A converter exit failure leaves no catalog record.
- Zero or multiple Markdown results is a converter-contract failure; inspect
  the temporary output pattern before changing the library.
- A referenced missing image is a conversion failure, not a reason to drop the
  image link silently.
- Run `ingest --dry-run` first to inspect inferred metadata and duplicates; it
  intentionally does not start the converter.

## MinerU

MinerU is supported as a convenience adapter when `mineru` is on `PATH` or
provided with `--mineru`. Its installation, model downloads, GPU selection,
and resource requirements belong to MinerU's own documentation. They are not
PaperMason installation requirements.
