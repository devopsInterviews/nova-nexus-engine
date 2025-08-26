from dotenv import load_dotenv
from app.client import app
import uvicorn
import os

load_dotenv()

# Configuration
CLIENT_HOST    = os.getenv("CLIENT_HOST", "0.0.0.0")
CLIENT_PORT    = int(os.getenv("CLIENT_PORT", "8000"))

if __name__ == "__main__":


    # In prod, replace with:
    # gunicorn -k uvicorn.workers.UvicornWorker main:app --workers 4
    uvicorn.run("app.client:app", host=CLIENT_HOST, port=CLIENT_PORT, reload=True, log_config=None, log_level=None)