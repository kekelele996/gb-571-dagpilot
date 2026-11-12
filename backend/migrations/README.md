# migrations

- 运行时：backend 启动时 `Base.metadata.create_all()` 自动建表（`src/config/app.py`）。
- 本目录：`0001_initial.sql` 是与 ORM 等价的 MySQL 8.0 DDL，用于 DBA 预审索引 / 走正式迁移流程。
- 新增字段的约定：先改 `src/models/*`，再补一份 `000N_xxx.sql`，两处必须同源。
