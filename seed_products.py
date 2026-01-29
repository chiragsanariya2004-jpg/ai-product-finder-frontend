from database import SessionLocal
from models import Product

db = SessionLocal()

p1 = Product(name="HP Laptop", price=48000, rating=4.3, best_for="Students")
p2 = Product(name="Dell Laptop", price=52000, rating=4.4, best_for="Office")
p3 = Product(name="Lenovo Laptop", price=45000, rating=4.2, best_for="Coding")

db.add_all([p1, p2, p3])
db.commit()
db.close()

print("✅ Products inserted successfully")
