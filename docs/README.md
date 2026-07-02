# Documentation Index

This directory now separates active V1 documentation from historical phase artifacts.

## Active V1 Docs

| Directory | Use |
| --- | --- |
| `architecture/` | V1 system architecture and boundaries. |
| `roadmap/` | V1 delivery roadmap and completion status. |
| `backlog/` | V1 maintenance backlog and V2 idea parking lot. |
| `contracts/` | JSON report, provider trace, snapshot, and schema versioning contracts. |
| `ops/` | Scheduler automation and readiness semantics. |
| `releases/` | Release reports and verification evidence. |

## Archive

| Directory | Use |
| --- | --- |
| `archive/legacy-plans/` | Historical Phase 1-12 and V1 milestone implementation plans. |
| `archive/research/` | Initial open-source study and gap analysis. |
| `archive/reviews/` | Historical review/proposal outputs. |

Archived files are not part of the day-to-day V1 operating manual. They are retained for traceability and should not block future work.

## What Can Be Deleted Locally

These files are runtime or OS noise and should not be committed:

- `.DS_Store`
- `__pycache__/`
- `.pytest_cache/`
- `outputs/`
- `data/cache/`
- local `.venv/`

## What Should Not Be Deleted

- `README.md`
- `PROJECT_STRUCTURE.md`
- `docs/architecture/`
- `docs/roadmap/`
- `docs/backlog/`
- `docs/contracts/`
- `docs/ops/`
- `docs/releases/`

## Rule For Future Docs

New active docs should answer an operational question. If a document is mainly a past implementation plan or research note, put it under `docs/archive/`.
