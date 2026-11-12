-- dagpilot 初始结构（MySQL 8.0）
-- 运行时由 SQLAlchemy Base.metadata.create_all 建表；此文件是等价 DDL，
-- 供 DBA 走迁移流程 / 预审索引用，字段与 src/models 一一对应。

CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  email         VARCHAR(160) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  display_name  VARCHAR(80)  NOT NULL,
  role          VARCHAR(20)  NOT NULL,
  created_at    DATETIME     NOT NULL,
  UNIQUE KEY uq_users_email (email),
  KEY ix_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pipelines (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  code       VARCHAR(40) NOT NULL,
  name       VARCHAR(80) NOT NULL,
  line_no    VARCHAR(8)  NOT NULL,
  line_color VARCHAR(40) NOT NULL,
  start_clock VARCHAR(5) NOT NULL,
  crew       VARCHAR(60) NOT NULL,
  note       TEXT,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_pipelines_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS jobs (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  code         VARCHAR(64)  NOT NULL,
  name         VARCHAR(120) NOT NULL,
  pipeline_id  INT NOT NULL,
  layer        VARCHAR(16) NOT NULL,
  owner        VARCHAR(60) NOT NULL,
  target_table VARCHAR(120),
  p50_seconds  INT NOT NULL,
  p90_seconds  INT NOT NULL,
  status       VARCHAR(16) NOT NULL DEFAULT 'active',
  note         TEXT,
  updated_at   DATETIME NOT NULL,
  UNIQUE KEY uq_jobs_code (code),
  KEY ix_jobs_pipeline (pipeline_id),
  KEY ix_jobs_layer (layer),
  CONSTRAINT fk_jobs_pipeline FOREIGN KEY (pipeline_id) REFERENCES pipelines (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dependencies (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  pipeline_id       INT NOT NULL,
  upstream_job_id   INT NOT NULL,
  downstream_job_id INT NOT NULL,
  dep_type          VARCHAR(16) NOT NULL DEFAULT 'data',
  lag_minutes       INT NOT NULL DEFAULT 0,
  created_at        DATETIME NOT NULL,
  UNIQUE KEY uq_dependency_edge (pipeline_id, upstream_job_id, downstream_job_id),
  KEY ix_dep_upstream (upstream_job_id),
  KEY ix_dep_downstream (downstream_job_id),
  CONSTRAINT fk_dep_pipeline FOREIGN KEY (pipeline_id) REFERENCES pipelines (id),
  CONSTRAINT fk_dep_upstream FOREIGN KEY (upstream_job_id) REFERENCES jobs (id),
  CONSTRAINT fk_dep_downstream FOREIGN KEY (downstream_job_id) REFERENCES jobs (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  pipeline_id     INT NOT NULL,
  mode            VARCHAR(8) NOT NULL DEFAULT 'p50',
  run_kind        VARCHAR(16) NOT NULL DEFAULT 'simulation',
  status          VARCHAR(16) NOT NULL DEFAULT 'simulated',
  run_date        DATE NULL,
  total_minutes   INT NOT NULL DEFAULT 0,
  p50_minutes     INT NOT NULL DEFAULT 0,
  p90_minutes     INT NOT NULL DEFAULT 0,
  peak_concurrency INT NOT NULL DEFAULT 0,
  critical_path   JSON,
  job_timings     JSON,
  sla_verdict     JSON,
  triggered_by    VARCHAR(120) NOT NULL DEFAULT 'system',
  seed_key        VARCHAR(120) NULL,
  created_at      DATETIME NOT NULL,
  UNIQUE KEY uq_runs_seed_key (seed_key),
  KEY ix_runs_pipeline (pipeline_id),
  KEY ix_runs_kind (run_kind),
  KEY ix_runs_created (created_at),
  CONSTRAINT fk_runs_pipeline FOREIGN KEY (pipeline_id) REFERENCES pipelines (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sla_policies (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  pipeline_id    INT NOT NULL,
  name           VARCHAR(80) NOT NULL,
  deadline_clock VARCHAR(5)  NOT NULL,
  buffer_minutes INT NOT NULL DEFAULT 30,
  owner_team     VARCHAR(80) NOT NULL,
  consumer       VARCHAR(120) NOT NULL,
  enabled        TINYINT(1) NOT NULL DEFAULT 1,
  note           TEXT,
  updated_at     DATETIME NOT NULL,
  UNIQUE KEY uq_sla_pipeline (pipeline_id),
  CONSTRAINT fk_sla_pipeline FOREIGN KEY (pipeline_id) REFERENCES pipelines (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  actor_email VARCHAR(160) NOT NULL,
  actor_role  VARCHAR(20)  NOT NULL,
  action      VARCHAR(64)  NOT NULL,
  entity      VARCHAR(40)  NOT NULL,
  entity_id   VARCHAR(64)  NULL,
  detail      JSON,
  layer       VARCHAR(16) NOT NULL DEFAULT 'domain',
  ip          VARCHAR(64) NULL,
  seed_key    VARCHAR(120) NULL,
  created_at  DATETIME NOT NULL,
  UNIQUE KEY uq_audit_seed_key (seed_key),
  KEY ix_audit_actor (actor_email),
  KEY ix_audit_action (action),
  KEY ix_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
