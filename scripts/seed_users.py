import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from main import Session, User, hash_pw, config

def add_user(name, email, password, role="student", **profile):
    with Session() as s:
        existing = s.query(User).filter_by(email=email.lower()).first()
        if existing:
            print(f"User '{email}' already exists (Role: {existing.role})")
            return
        user = User(
            name=name,
            email=email.lower(),
            pw=hash_pw(password),
            role=role.lower(),
            active=True,
            **profile
        )
        s.add(user)
        s.commit()
        print(f"Successfully added {role.upper()}: '{name}' ({email})")

if __name__ == "__main__":
    print("CrossMind User Seeder")
    print("---------------------")
    # Example Seed Users:
    add_user("Prof. Alan Turing", "turing@crossmind.edu", "TeacherPass123", role="teacher", department="Computer Science", employee_id="T-001")
    add_user("Prof. Ada Lovelace", "ada@crossmind.edu", "TeacherPass123", role="teacher", department="Mathematics", employee_id="T-002")
    add_user("Sujal Patil", "sujal@student.edu", "StudentPass123", role="student")
    add_user("Rahul Sharma", "rahul@student.edu", "StudentPass123", role="student")
    add_user("Priya Patel", "priya@student.edu", "StudentPass123", role="student")
