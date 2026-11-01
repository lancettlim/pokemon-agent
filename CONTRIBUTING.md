# Contributing

Thanks for helping. Bug reports, data corrections and small fixes are all
welcome.

## Reporting a problem

Use the issue templates:

- **Bug report**: the dashboard or a pipeline does something wrong.
- **Data correction**: a number, name, set or result looks wrong. Say which
  view or table, what you expected, and a source if you have one.

## Making a change

```bash
make setup   # uv sync + Chromium
make check   # lint, unit tests, dbt build/test, validation report
```

- `make lint` and `make test` need no network and run fast.
- `data/` is generated and gitignored. `docs/dashboard/` is generated but
  committed: run `make dashboard` after touching `pipelines/dashboard/`.
- Read `CLAUDE.md` first. The rules that matter most:
  - Every record carries provenance (`source_name`, `source_url`,
    `source_record_id`, `extracted_at_utc`, `dataset_version`).
  - Regulations live in `dbt/seeds/champions_regulations.csv` only; never
    hardcode a format string.
  - Online and ladder data are separate populations and are never blended
    into official figures.
  - Tournament data has no EV or Stat Point fields; match results are team
    vs team.
- Keep a PR to one concern. Update the relevant doc in `docs/` when scope,
  schema or refresh policy changes.

By contributing you agree your code is released under the MIT license.
