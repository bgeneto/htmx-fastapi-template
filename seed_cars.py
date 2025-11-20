"""
Seed the database with fake car data using Faker
Run: python seed_cars.py
"""
import asyncio
import random
from sqlalchemy.ext.asyncio import AsyncSession
from faker import Faker

from app.db import engine
from app.models import Car
from sqlalchemy.orm import sessionmaker

fake = Faker()

# Car data
MAKES = ["Toyota", "Honda", "Ford", "Tesla", "BMW", "Mercedes-Benz", "Audi", "Volkswagen", "Nissan", "Hyundai", "Kia", "Mazda", "Subaru", "Chevrolet", "Dodge"]
MODELS = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Tacoma"],
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "Odyssey"],
    "Ford": ["F-150", "Mustang", "Explorer", "Escape", "Bronco"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y"],
    "BMW": ["3 Series", "5 Series", "X3", "X5", "M4"],
    "Mercedes-Benz": ["C-Class", "E-Class", "GLE", "GLC", "S-Class"],
    "Audi": ["A4", "A6", "Q5", "Q7", "e-tron"],
    "Volkswagen": ["Golf", "Jetta", "Tiguan", "Passat", "Atlas"],
    "Nissan": ["Altima", "Sentra", "Rogue", "Pathfinder", "Frontier"],
    "Hyundai": ["Elantra", "Sonata", "Tucson", "Santa Fe", "Palisade"],
    "Kia": ["Forte", "Optima", "Sportage", "Sorento", "Telluride"],
    "Mazda": ["Mazda3", "Mazda6", "CX-5", "CX-9", "MX-5"],
    "Subaru": ["Impreza", "Legacy", "Outback", "Forester", "Crosstrek"],
    "Chevrolet": ["Malibu", "Silverado", "Equinox", "Traverse", "Blazer"],
    "Dodge": ["Charger", "Challenger", "Durango", "Ram 1500", "Journey"]
}
VERSIONS = ["Base", "LE", "SE", "Sport", "Limited", "Premium", "Luxury", "Platinum", "Turbo", "Hybrid", "Electric"]

async def seed_database(count: int = 200):
    """Seed database with fake car data"""
    
    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Check existing count
        from sqlmodel import select
        result = await session.execute(select(Car))
        existing_cars = result.scalars().all()
        
        if existing_cars:
            print(f"⚠️  Database already has {len(existing_cars)} cars.")
            response = input("Delete all and reseed? (y/N): ")
            if response.lower() == 'y':
                for car in existing_cars:
                    await session.delete(car)
                await session.commit()
                print("✅ Deleted all existing cars")
            else:
                print("❌ Seeding cancelled")
                return
        
        print(f"🌱 Seeding {count} cars...")
        
        cars = []
        for i in range(count):
            make = random.choice(MAKES)
            model = random.choice(MODELS.get(make, ["Unknown"]))
            version = random.choice(VERSIONS)
            year = random.randint(2015, 2024)
            
            # Price based on year and make
            base_price = 20000
            if make in ["Tesla", "BMW", "Mercedes-Benz", "Audi"]:
                base_price = 40000
            
            price = base_price + (year - 2015) * 2000 + random.randint(-5000, 15000)
            
            car = Car(
                make=make,
                model=model,
                version=version,
                year=year,
                price=float(price)
            )
            cars.append(car)
        
        session.add_all(cars)
        await session.commit()
        
        print(f"✅ Successfully seeded {count} cars!")
        print("\n📊 Sample data:")
        for car in cars[:5]:
            print(f"   - {car.year} {car.make} {car.model} {car.version} - ${car.price:,.2f}")

if __name__ == "__main__":
    asyncio.run(seed_database(200))
