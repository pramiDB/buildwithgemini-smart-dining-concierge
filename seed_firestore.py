"""Seed script for Smart Dining Concierge Firestore database."""

from google.cloud import firestore

# Hardcoded project ID as required to prevent Agent Platform project number resolution issues
PROJECT_ID = "qwiklabs-gcp-01-e2b12085102f"

SAMPLE_MENU_ITEMS = [
    {
        "id": "dish_001",
        "name": "Truffle Mushroom Risotto",
        "category": "Main",
        "cuisine": "Italian",
        "price": 24.50,
        "dietary": ["vegetarian", "gluten-free"],
        "description": "Arborio rice cooked with wild mushrooms, black truffle oil, and aged Parmesan cheese.",
        "calories": 580,
        "spice_level": 0,
    },
    {
        "id": "dish_002",
        "name": "Spicy Thai Green Curry",
        "category": "Main",
        "cuisine": "Thai",
        "price": 19.99,
        "dietary": ["vegan", "dairy-free"],
        "description": "Coconut curry with bamboo shoots, Thai basil, and tofu served over jasmine rice.",
        "calories": 620,
        "spice_level": 3,
    },
    {
        "id": "dish_003",
        "name": "Pan-Seared Atlantic Salmon",
        "category": "Main",
        "cuisine": "Seafood",
        "price": 28.00,
        "dietary": ["gluten-free", "pescatarian"],
        "description": "Fresh salmon fillet with lemon herb butter, roasted asparagus, and quinoa pilaf.",
        "calories": 510,
        "spice_level": 0,
    },
    {
        "id": "dish_004",
        "name": "Avocado & Citrus Salad",
        "category": "Appetizer",
        "cuisine": "Mediterranean",
        "price": 14.50,
        "dietary": ["vegan", "gluten-free", "nut-free"],
        "description": "Mixed greens, sliced avocado, grapefruits, pomegranate seeds, and citrus vinaigrette.",
        "calories": 310,
        "spice_level": 0,
    },
    {
        "id": "dish_005",
        "name": "Matcha Lava Cake",
        "category": "Dessert",
        "cuisine": "Japanese Fusion",
        "price": 12.00,
        "dietary": ["vegetarian"],
        "description": "Warm green tea molten chocolate cake with black sesame ice cream.",
        "calories": 450,
        "spice_level": 0,
    },
]


def seed_database():
    print(f"Connecting to Firestore for project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID, database="smart-dining-db")
    collection_ref = db.collection("menu_items")

    for item in SAMPLE_MENU_ITEMS:
        doc_ref = collection_ref.document(item["id"])
        doc_ref.set(item)
        print(f"Seeded dish: {item['name']} ({item['id']})")

    print("Firestore seeding complete!")


if __name__ == "__main__":
    seed_database()
