CREATE TABLE users (
  id uuid PRIMARY KEY,
  email varchar(100) NOT NULL UNIQUE CHECK (email = lower(trim(email))),
  name varchar(30) NOT NULL,
  password_hash varchar(100) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE courses (
  id varchar(30) PRIMARY KEY,
  sort_order integer NOT NULL UNIQUE,
  code varchar(20) NOT NULL UNIQUE,
  name varchar(100) NOT NULL,
  professor varchar(30) NOT NULL,
  department varchar(30) NOT NULL,
  capacity integer NOT NULL CHECK (capacity > 0),
  reserved_count integer NOT NULL CHECK (reserved_count >= 0),
  enrolled_count integer NOT NULL,
  CHECK (enrolled_count >= reserved_count AND enrolled_count <= capacity)
);
CREATE TABLE enrollments (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id),
  course_id varchar(30) NOT NULL REFERENCES courses(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, course_id)
);
CREATE INDEX enrollment_course_idx ON enrollments(course_id);
CREATE TABLE registration_window (
  id integer PRIMARY KEY CHECK (id=1),
  is_open boolean NOT NULL DEFAULT false
);
INSERT INTO registration_window(id, is_open) VALUES (1,false);
CREATE TABLE auth_sessions (
  token_hash char(64) PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX auth_session_expiry_idx ON auth_sessions(expires_at);
