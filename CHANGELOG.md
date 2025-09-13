# CHANGELOG.md

All notable changes to this project will be documented in this file.

## [Unreleased]
- Ongoing refactor for maintainability and best practices (Phase 3)

## [1.0.1] - 2025-09-13
- Major backend refactor: extracted service layer, modernized error handling, improved type annotations, and centralized business logic.
- All routers now delegate to service modules.
- Introduced `utils/error_handling.py` for structured error handling and logging.
- Added/updated Pydantic models for all request/response schemas.
- Improved async correctness and code documentation.

## [Older versions]
- See project history for earlier changes.
