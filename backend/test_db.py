import asyncio
from database import AsyncSessionLocal, Job
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Job))
        jobs = result.scalars().all()
        for j in jobs:
            print(f"Job: {j.id}, Status: {j.status.value}, Error: {j.error_message}")

asyncio.run(main())
