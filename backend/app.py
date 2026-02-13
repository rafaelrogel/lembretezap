"""FastAPI app: health (token opcional) + rotas protegidas por API key e CORS configurável."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routes import router

# Health: só responde 200 com X-Health-Token quando HEALTH_CHECK_TOKEN está definido
HEALTH_CHECK_TOKEN = os.environ.get("HEALTH_CHECK_TOKEN", "").strip() or None

# CORS: em produção definir CORS_ORIGINS (ex.: https://app.seudominio.com); vazio ou * = permitir todas
CORS_ORIGINS_RAW = os.environ.get("CORS_ORIGINS", "*").strip()
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_RAW.split(",") if o.strip()] if CORS_ORIGINS_RAW else ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Zapista API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health(x_health_token: str | None = Header(None, alias="X-Health-Token")) -> dict:
    """Health check. Com HEALTH_CHECK_TOKEN definido, exige header X-Health-Token (acesso interno)."""
    if HEALTH_CHECK_TOKEN and x_health_token != HEALTH_CHECK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"status": "ok"}
