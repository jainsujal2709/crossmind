import datetime as dt
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker
import config

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True
)
Session = sessionmaker(bind=engine)
Base = declarative_base()

now = lambda: dt.datetime.utcnow()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    pw = Column(String)
    role = Column(String, default="student") # student, teacher, admin
    active = Column(Boolean, default=True)
    created = Column(DateTime, default=now)

class Doc(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String)
    segs = Column(JSON)
    created = Column(DateTime, default=now)

class Puzzle(Base):
    __tablename__ = "crosswords"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    title = Column(String)
    difficulty = Column(String, index=True)
    data = Column(JSON)
    done = Column(Boolean, default=False)
    score = Column(Float)
    secs = Column(Integer)
    hints = Column(Integer, default=0)
    created = Column(DateTime, default=now)

class Classroom(Base):
    __tablename__ = "classrooms"
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    division = Column(String, default="")
    description = Column(Text, default="")
    code = Column(String, unique=True, index=True, nullable=False) # e.g. DSB472
    created = Column(DateTime, default=now)

class ClassroomMember(Base):
    __tablename__ = "classroom_members"
    id = Column(Integer, primary_key=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), index=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True)
    joined_at = Column(DateTime, default=now)

class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), index=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), index=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    title = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    difficulty = Column(String, default="medium") # easy, medium, hard
    time_limit = Column(Integer, default=15) # in minutes
    questions = Column(JSON, nullable=False) # list of Q objects
    controls = Column(JSON, default=dict) # randomize, hints, privacy, retakes, etc.
    is_active = Column(Boolean, default=False)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created = Column(DateTime, default=now)

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), index=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True)
    score = Column(Float, default=0.0) # total points
    percentage = Column(Float, default=0.0) # 0 to 100
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    time_taken_secs = Column(Integer, default=0)
    answers = Column(JSON, nullable=False) # user answers dict: {q_id: answer}
    submitted_at = Column(DateTime, default=now)

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    level = Column(String)
    msg = Column(Text)
    created = Column(DateTime, default=now)
