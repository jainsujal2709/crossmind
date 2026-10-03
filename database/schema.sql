-- CrossMind database schema (reference).
-- You do NOT need to run this by hand: the backend creates / upgrades these tables automatically
-- on startup (backend/models.py -> migrate()). This file documents the design and can be used to
-- create the database manually in PostgreSQL (Neon) if you prefer. SQLite also accepts it
-- if you replace SERIAL with INTEGER PRIMARY KEY AUTOINCREMENT and JSONB with TEXT.

-- ============================================================
-- USERS  (admins, teachers and students all live here)
--   role = 'admin'   -> created from ADMIN_EMAIL / ADMIN_PASSWORD env vars
--   role = 'teacher' -> created ONLY by an admin (no public registration)
--   role = 'student' -> self-registers on the website (or created by an admin)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id           SERIAL PRIMARY KEY,
    email        VARCHAR  NOT NULL UNIQUE,
    name         VARCHAR  NOT NULL,
    pw           VARCHAR  NOT NULL,                 -- bcrypt hash, never plain text
    role         VARCHAR  NOT NULL DEFAULT 'student' CHECK (role IN ('student','teacher','admin')),
    active       BOOLEAN  NOT NULL DEFAULT TRUE,    -- FALSE = login blocked
    created      TIMESTAMP DEFAULT now(),
    -- common profile
    phone        VARCHAR  DEFAULT '',
    last_login   TIMESTAMP,
    updated      TIMESTAMP,
    created_by   INTEGER,                           -- admin user id; NULL = self-registered
    -- teacher profile
    employee_id  VARCHAR  DEFAULT '',
    department   VARCHAR  DEFAULT '',
    subject      VARCHAR  DEFAULT '',
    -- student profile
    roll_no      VARCHAR  DEFAULT '',
    course       VARCHAR  DEFAULT '',
    division     VARCHAR  DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_users_role ON users(role);

-- ============================================================
-- LEARNING CONTENT
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (            -- uploaded / pasted study material
    id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), name VARCHAR,
    segs JSONB, created TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS crosswords (
    id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), title VARCHAR, difficulty VARCHAR,
    data JSONB, done BOOLEAN DEFAULT FALSE, score DOUBLE PRECISION, secs INTEGER,
    hints INTEGER DEFAULT 0, created TIMESTAMP DEFAULT now()
);

-- ============================================================
-- CLASSROOMS & QUIZZES
-- ============================================================
CREATE TABLE IF NOT EXISTS classrooms (
    id SERIAL PRIMARY KEY, teacher_id INTEGER REFERENCES users(id),
    name VARCHAR NOT NULL, subject VARCHAR NOT NULL, division VARCHAR DEFAULT '',
    description TEXT DEFAULT '', code VARCHAR NOT NULL UNIQUE, created TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS classroom_members (    -- which students joined which classroom
    id SERIAL PRIMARY KEY, classroom_id INTEGER REFERENCES classrooms(id),
    student_id INTEGER REFERENCES users(id), joined_at TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS quizzes (
    id SERIAL PRIMARY KEY, teacher_id INTEGER REFERENCES users(id),
    classroom_id INTEGER REFERENCES classrooms(id), doc_id INTEGER REFERENCES documents(id),
    title VARCHAR NOT NULL, topic VARCHAR NOT NULL, difficulty VARCHAR DEFAULT 'medium',
    time_limit INTEGER DEFAULT 15, questions JSONB NOT NULL, controls JSONB,
    is_active BOOLEAN DEFAULT FALSE, started_at TIMESTAMP, ended_at TIMESTAMP, created TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS quiz_attempts (        -- one row per student per quiz
    id SERIAL PRIMARY KEY, quiz_id INTEGER REFERENCES quizzes(id), student_id INTEGER REFERENCES users(id),
    score DOUBLE PRECISION DEFAULT 0, percentage DOUBLE PRECISION DEFAULT 0,
    correct_count INTEGER DEFAULT 0, wrong_count INTEGER DEFAULT 0, unanswered_count INTEGER DEFAULT 0,
    time_taken_secs INTEGER DEFAULT 0, answers JSONB NOT NULL, submitted_at TIMESTAMP DEFAULT now()
);

-- ============================================================
-- SYSTEM LOG (shown in Admin -> System Logs; also records admin create/edit/delete actions)
-- ============================================================
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY, level VARCHAR, msg TEXT, created TIMESTAMP DEFAULT now()
);

-- Handy queries for the admin ----------------------------------------------
-- All teachers:           SELECT id,name,email,department,employee_id,active FROM users WHERE role='teacher';
-- All students:           SELECT id,name,email,roll_no,course,division,active FROM users WHERE role='student';
-- Students per classroom: SELECT c.name, COUNT(m.id) FROM classrooms c LEFT JOIN classroom_members m ON m.classroom_id=c.id GROUP BY c.name;
