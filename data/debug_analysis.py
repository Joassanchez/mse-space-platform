import asyncio, httpx, json

async def test():
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("http://localhost:8000/api/v1/analysis", params={
            "lot_id": "lote-123", "crop": "soy",
            "lat": -33.9278607, "lon": -60.567172, "date": "2026-07-21",
        })
        data = r.json()
        # Show economy section
        eco = data.get("economy", {})
        print("=== ECONOMY ===")
        print(json.dumps(eco, indent=2, ensure_ascii=False))
        print()
        # Show agroclimate
        agro = data.get("agroclimate", {})
        print("=== AGROCLIMATE ===")
        print(json.dumps(agro, indent=2, ensure_ascii=False))
        print()
        # Show agronomy
        agron = data.get("agronomy", {})
        print("=== AGRONOMY ===")
        print(json.dumps(agron, indent=2, ensure_ascii=False))

asyncio.run(test())
