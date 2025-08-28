from dotenv import load_dotenv
from app.client import app
import uvicorn
import os

load_dotenv()

# Configuration
CLIENT_HOST    = os.getenv("CLIENT_HOST", "0.0.0.0")
CLIENT_PORT    = int(os.getenv("CLIENT_PORT", "8000"))
LOG_LEVEL      = os.getenv("LOG_LEVEL", "INFO").upper()

if __name__ == "__main__":
    # Get the logging config file path
    logging_config_path = os.path.join(os.path.dirname(__file__), "logging_config.json")
    
    # Run uvicorn with custom logging configuration
    uvicorn.run(
        "app.client:app", 
        host=CLIENT_HOST, 
        port=CLIENT_PORT, 
        reload=True, 
        log_config=logging_config_path,
        log_level=LOG_LEVEL.lower()
    )