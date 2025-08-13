from db import init_db, SessionLocal, User, Role
import bcrypt

def add_user(name, email, password, role):
    db = SessionLocal()
    if db.query(User).filter(User.email==email).first():
        print(f"User {email} exists. Skipping.")
        return
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    u = User(name=name, email=email, password_hash=pw_hash, role=Role(role))
    db.add(u)
    db.commit()
    print(f"Created {email} ({role})")

def main():
    init_db()
    add_user("Admin", "admin@example.com", "admin123", "admin")
    add_user("Manager Kim", "mgr@example.com", "mgr123", "manager")
    add_user("HR Lee", "hr@example.com", "hr123", "hr")
    add_user("Finance Park", "fin@example.com", "fin123", "finance")
    add_user("Leaver Choi", "leaver@example.com", "leaver123", "leaver")

if __name__ == "__main__":
    main()
