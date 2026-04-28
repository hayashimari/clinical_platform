from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.search_service import search_documents

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    answer_mode: str = "clinical_summary"


@router.post("/search")
def search(req: SearchRequest):
    try:
        return search_documents(None, req.query)
    except Exception as e:
        print("SEARCH ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
