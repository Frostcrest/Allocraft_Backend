from app.main import app
from fastapi.openapi.utils import get_openapi
import json
from pathlib import Path

if __name__ == "__main__":
    schema = get_openapi(
        title=app.title,
        version="1.0.0",
        routes=app.routes,
        description="Generated OpenAPI schema"
    )
    out_dir = Path(__file__).parents[2] / "docs" / "API"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "openapi.json"
    out_file.write_text(json.dumps(schema, indent=2))
    print(f"Wrote OpenAPI to {out_file}")
