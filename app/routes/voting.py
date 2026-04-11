# Voting is handled via the books routes (approve/withdraw).
# This module is reserved for future voting-specific endpoints
# (e.g., a dedicated voting page separate from the book list).

from fastapi import APIRouter

router = APIRouter()
