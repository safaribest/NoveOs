-- Novel-OS World State Schema
-- SQLite 表结构定义，用于跨章状态持久化（多项目版本）

-- 0. 项目注册表（Orchestrator 用）
CREATE TABLE IF NOT EXISTS projects (
    project_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    genre           TEXT NOT NULL,
    platform        TEXT NOT NULL,
    base_path       TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    current_chapter INTEGER DEFAULT 0,
    total_chapters  INTEGER NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 运行日志表（供前端查询历史日志）
CREATE TABLE IF NOT EXISTS runtime_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    log_id      TEXT NOT NULL,
    level       TEXT NOT NULL,
    agent       TEXT NOT NULL,
    chapter_num INTEGER,
    message     TEXT NOT NULL,
    metadata    TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX IF NOT EXISTS idx_logs_project ON runtime_logs(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_agent ON runtime_logs(project_id, agent);

-- 1. 人物状态表（每章快照）
CREATE TABLE IF NOT EXISTS character_states (
    project_id      TEXT NOT NULL,
    chapter         INTEGER NOT NULL,
    character_name  TEXT NOT NULL,
    location        TEXT,
    emotional_state TEXT,
    known_secrets   TEXT,          -- JSON 数组
    unknown_secrets TEXT,          -- JSON 数组
    abilities_active TEXT,         -- JSON 数组
    abilities_locked TEXT,         -- JSON 数组
    dialog_fingerprint TEXT,
    body_language   TEXT,
    physical_description TEXT,
    PRIMARY KEY (project_id, chapter, character_name),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX IF NOT EXISTS idx_char_name_chapter ON character_states(project_id, character_name, chapter);

-- 2. 道具状态表
CREATE TABLE IF NOT EXISTS item_states (
    project_id  TEXT NOT NULL,
    chapter     INTEGER NOT NULL,
    item_name   TEXT NOT NULL,
    location    TEXT,
    state       TEXT,
    rule        TEXT,                   -- JSON 数组，约束规则
    state_history TEXT,                 -- JSON 数组，状态变更历史
    PRIMARY KEY (project_id, chapter, item_name),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX IF NOT EXISTS idx_item_name_chapter ON item_states(project_id, item_name, chapter);

-- 3. 债务表（伏笔的一种，必须回收）
CREATE TABLE IF NOT EXISTS debts (
    project_id      TEXT NOT NULL,
    debt_id         TEXT NOT NULL,
    type            TEXT,
    content         TEXT NOT NULL,
    bury_chapter    INTEGER NOT NULL,
    collect_chapter INTEGER,
    status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'collected', 'abandoned')),
    PRIMARY KEY (project_id, debt_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX IF NOT EXISTS idx_debt_collect ON debts(project_id, status, collect_chapter);
CREATE INDEX IF NOT EXISTS idx_debt_bury ON debts(project_id, bury_chapter);

-- 4. 伏笔总表
CREATE TABLE IF NOT EXISTS foreshadowing (
    project_id      TEXT NOT NULL,
    fs_id           TEXT NOT NULL,
    bury_chapter    INTEGER NOT NULL,
    content         TEXT NOT NULL,
    collect_chapter TEXT,               -- 支持 "3/10" 多章回收格式
    type            TEXT,
    status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'collected', 'abandoned')),
    PRIMARY KEY (project_id, fs_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX IF NOT EXISTS idx_fs_collect ON foreshadowing(project_id, status, collect_chapter);
CREATE INDEX IF NOT EXISTS idx_fs_bury ON foreshadowing(project_id, bury_chapter);

-- 5. 配角出场调度表
CREATE TABLE IF NOT EXISTS cast_schedule (
    project_id      TEXT NOT NULL,
    character_name  TEXT NOT NULL,
    chapter         INTEGER NOT NULL,
    must_appear     BOOLEAN DEFAULT 0,
    role_evolution  TEXT,
    dialog_fingerprint TEXT,
    physical_description TEXT,
    PRIMARY KEY (project_id, character_name, chapter),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX IF NOT EXISTS idx_cast_chapter ON cast_schedule(project_id, chapter);

-- 6. 情感坐标历史表
CREATE TABLE IF NOT EXISTS emotion_history (
    project_id      TEXT NOT NULL,
    chapter         INTEGER NOT NULL,
    mode            TEXT,
    nue_density     REAL,               -- 虐密度 0.0~1.0
    tian_density    REAL,               -- 甜密度 0.0~1.0
    shuang_density  REAL,               -- 爽密度 0.0~1.0
    coordinate_x    REAL,               -- 情感坐标 X（横轴：压抑<->释放）
    coordinate_y    REAL,               -- 情感坐标 Y（纵轴：虐<->甜）
    desc            TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, chapter),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- 7. 章节快照表（用于回滚）
CREATE TABLE IF NOT EXISTS chapter_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      TEXT NOT NULL,
    chapter         INTEGER NOT NULL,
    snapshot_type   TEXT NOT NULL,      -- pre_write / post_write / manual
    snapshot_data   TEXT NOT NULL,      -- JSON
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX IF NOT EXISTS idx_snapshot_chapter_type ON chapter_snapshots(project_id, chapter, snapshot_type);
CREATE INDEX IF NOT EXISTS idx_snapshot_created ON chapter_snapshots(created_at);

-- 8. 跨章一致性约束表
CREATE TABLE IF NOT EXISTS consistency_rules (
    project_id          TEXT NOT NULL,
    rule_type           TEXT NOT NULL,
    rule_content        TEXT NOT NULL,
    enforcement_level   TEXT DEFAULT 'hard' CHECK (enforcement_level IN ('hard', 'soft', 'info')),
    PRIMARY KEY (project_id, rule_type, rule_content),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
CREATE INDEX IF NOT EXISTS idx_rule_type ON consistency_rules(project_id, rule_type);

-- 9. 章节历史表（已写章节摘要）
CREATE TABLE IF NOT EXISTS chapter_history (
    project_id      TEXT NOT NULL,
    chapter         INTEGER NOT NULL,
    summary         TEXT,
    word_count      INTEGER,
    mode            TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, chapter),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
