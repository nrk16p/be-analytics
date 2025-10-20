from fastapi import Header, HTTPException, status
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")

def verify_token(x_token: str = Header(...)):
    """
    🔐 Verify the fixed API token from the request header.
    Add this header to all requests:
        x-token: <your API_TOKEN>
    """
    if not API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: API_TOKEN not set in .env"
        )

    if x_token != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token"
        )
