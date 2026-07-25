import asyncio, httpx, json

async def test():
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post("http://localhost:8000/api/v1/predict", json={
            "lot_id": "lote-123", "crop": "soy",
            "lat": -33.9278607, "lon": -60.567172, "date": "2026-07-21",
        })
        d = r.json()
        print("=== ECONOMIC IMPACT ===")
        print(json.dumps(d.get("economic_impact", {}), indent=2))

asyncio.run(test())
