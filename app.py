"""
Entrypoint FastAPI para o backend (frontend irmão).
Rodar local: python app.py ou uvicorn backend.app:app --reload --port 8000
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
