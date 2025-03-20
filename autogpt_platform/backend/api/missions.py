# backend/api/missions.py

print("✅ Scrapy router loaded")



from fastapi import APIRouter, Request
from backend.scrapy.mission_runner import run_scrapy_mission



router = APIRouter()

@router.post("/scrapy")
async def trigger_scrapy(request: Request):
    payload = await request.json()
    result = run_scrapy_mission(payload)
    return result


