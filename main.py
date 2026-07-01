import os
import time
import uuid

import jwt
import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

# =========================
# Configuration
# =========================

EMAIL = "22f3000996@ds.study.iitm.ac.in"

ALLOWED_ORIGIN = "https://dash-dh6obe.example.com"

ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-ges2vabw.apps.exam.local"

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI()

# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Middleware
# =========================

class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()

        response = await call_next(request)

        process_time = time.perf_counter() - start

        response.headers["X-Request-ID"] = str(uuid.uuid4())
        response.headers["X-Process-Time"] = f"{process_time:.6f}"

        return response


app.add_middleware(RequestMiddleware)

# =========================
# Question 1
# =========================

@app.get("/stats")
async def stats(values: str = Query(...)):
    nums = [int(x.strip()) for x in values.split(",") if x.strip()]

    return {
        "email": EMAIL,
        "count": len(nums),
        "sum": sum(nums),
        "min": min(nums),
        "max": max(nums),
        "mean": sum(nums) / len(nums),
    }

# =========================
# Question 2
# =========================

class TokenRequest(BaseModel):
    token: str


@app.post("/verify")
async def verify(req: TokenRequest):
    try:
        payload = jwt.decode(
            req.token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
        )

        return {
            "valid": True,
            "email": payload.get("email"),
            "sub": payload.get("sub"),
            "aud": payload.get("aud"),
        }

    except jwt.PyJWTError:
        return JSONResponse(
            status_code=401,
            content={"valid": False},
        )

# =========================
# Question 3
# =========================

def to_bool(value):
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def convert(key, value):
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        return to_bool(value)
    return str(value)


@app.get("/effective-config")
async def effective_config(request: Request):
    cfg = DEFAULTS.copy()

    # YAML layer
    if os.path.exists("config.development.yaml"):
        with open("config.development.yaml", "r") as f:
            data = yaml.safe_load(f) or {}
            for k, v in data.items():
                cfg[k] = convert(k, v)

    # .env layer
    env_data = dotenv_values(".env")
    for k, v in env_data.items():
        if v is None:
            continue

        if k == "NUM_WORKERS":
            cfg["workers"] = convert("workers", v)
        elif k.startswith("APP_"):
            key = k[4:].lower()
            cfg[key] = convert(key, v)

    # OS environment variables
    for k, v in os.environ.items():
        if not k.startswith("APP_"):
            continue

        key = k[4:].lower()
        cfg[key] = convert(key, v)

    # CLI overrides
    for item in request.query_params.getlist("set"):
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        cfg[key] = convert(key, value)

    # Mask API key
    cfg["api_key"] = "****"

    return cfg