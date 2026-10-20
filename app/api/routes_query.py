"""Question answering route with the verification boundary in the service."""

from fastapi import APIRouter, HTTPException

from app.api.schemas import QueryRequest, QueryResponse
from app.services.retrieval_service import search_and_answer

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query_documents(request: QueryRequest) -> QueryResponse:
    """Run hybrid search, verify selected evidence, then generate an answer."""
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty")
    try:
        result = search_and_answer(request.question.strip())
    except ValueError as error:
        if str(error) == "Tampered or unverified context":
            raise HTTPException(status_code=403, detail=str(error)) from error
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return QueryResponse(**result)
