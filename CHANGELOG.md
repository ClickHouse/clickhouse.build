# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0-prototype] - 2025-11-24

### Added
- Initial prototype release of clickhouse.build
- Scanner agent for discovering PostgreSQL analytical queries
- Data migrator agent for generating ClickPipe configurations
- Code migrator agent for transforming application code to use ClickHouse
- QA code migrator agent for validating code quality
- Support for multiple ORMs (Prisma, Drizzle, raw SQL)
- Rich terminal UI with progress indicators and colored output
- Comprehensive tool system (grep, glob, read, write, bash)
- Evaluation framework for testing agent performance
- Three example test applications with different ORM patterns
- User approval workflow for all file writes and bash commands

### Notes
- This is an experimental prototype release
- AI-generated code requires human review before deployment
- Requires AWS credentials and Bedrock access for Claude Sonnet 4.5
- Python 3.13+ required

[Unreleased]: https://github.com/ClickHouse/clickhouse.build/compare/v0.1.0-prototype...HEAD
[0.1.0-prototype]: https://github.com/ClickHouse/clickhouse.build/releases/tag/v0.1.0-prototype
