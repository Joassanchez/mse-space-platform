"""Debug: test RawFileDiscoveryRepository directly."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["PGHOST"] = "localhost"
os.environ["PGPORT"] = "5432"
os.environ["PGDATABASE"] = "mse_platform"
os.environ["PGUSER"] = "mse_user"
os.environ["PGPASSWORD"] = "mse_pass"

from src.geospatial.infrastructure.persistence.postgres_repositories import RawFileDiscoveryRepositoryImpl

repo = RawFileDiscoveryRepositoryImpl()

result = repo.find_completed(source="smap", limit=5)
print("Files found:", len(result))
for f in result:
    print(" ", f["id"], f["file_name"])
