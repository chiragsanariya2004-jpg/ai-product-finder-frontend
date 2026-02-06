from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests
from dotenv import load_dotenv
import json
from database import engine, SessionLocal, Base
from models import Product
from fastapi import Depends
from sqlalchemy.orm import Session

# env load
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI()
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# test route
@app.get("/")
def home():
    return {"message": "AI Product Finder API is running"}

@app.get("/products")
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return products

@app.post("/seed")
def seed_products(db: Session = Depends(get_db)):
    db.query(Product).delete()

    products = [
        Product(name="Redmi Note 13", price=12000, rating=4.2, best_for="Budget users"),
        Product(name="Samsung Galaxy M14", price=13500, rating=4.3, best_for="Battery life"),
        Product(name="Realme Narzo 60", price=15000, rating=4.1, best_for="Performance"),
    ]

    db.add_all(products)
    db.commit()
    return {"message": "Products seeded successfully"}


# request body structure
class ProductRequest(BaseModel):
    query: str
    budget: int

# main AI route
@app.post("/find-product")
def find_product(
    data: ProductRequest,
    db: Session = Depends(get_db)
 ):
   
    if not GROQ_API_KEY:
        return {
            "error": "GROQ_API_KEY missing"
        }

    query = data.query
    budget = data.budget

    filtered_products = (
    db.query(Product)
    .filter(Product.price <= budget)
    .filter(Product.name.ilike(f"%{query}%"))
    .limit(3)
    .all()
)

    products_text = ""
    for p in filtered_products:
        products_text += (
            f"- {p.name}, price {p.price}, "
            f"rating {p.rating}, best for {p.best_for}\n"
        )
        
    prompt = f"""
You are an AI product comparison assistant.

User query: {query}
Budget: {budget}

Available products:
{products_text}

Respond ONLY in valid JSON format.

JSON structure must be exactly like this:

{{
  "products": [
    {{
      "name": "Product name",
      "price": 0,
      "rating": 0,
      "best_for": "Reason",
      "pros": ["point 1", "point 2"],
      "cons": ["point 1"]
    }}
  ],
  "final_recommendation": "Product name",
  "reason": "Short reason"
}}

Rules:
- Price must be under the given budget
- Recommend 3 products only
- Do not add any extra text outside JSON
"""




    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
    )

    try:
        result = response.json()
    except Exception:
        return {
            "error": "Groq returned non‑JSON response",
            "raw": response.text
        }

    if response.status_code != 200:
        return {
            "error": "Groq API error",
            "status_code": response.status_code,
            "groq_response": result
        }

    if "choices" not in result:
        return {
            "error": "Unexpected Groq response format",
            "groq_response": result
        }

    ai_text = result["choices"][0]["message"]["content"]

    try:
        ai_json = json.loads(ai_text)
    except json.JSONDecodeError:
        return {
            "error": "AI response is not valid JSON",
            "raw_ai_reply": ai_text
        }
    
    # 🔒 SAFETY FILTER (budget cross na ho)
    safe_products = [
        p for p in ai_json.get("products", [])
        if p.get("price", 0) <= budget
]

    if not safe_products:
        return {
            "query": data.query,
            "budget": data.budget,
            "products": [],
            "final_recommendation": "No product found",
            "reason": "No products available within the given budget"
        }

    return {
        "query": data.query,
        "budget": data.budget,
        "products": safe_products,
        "final_recommendation": safe_products[0]["name"],
        "reason": ai_json.get("reason")
    }
