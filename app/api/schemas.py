"""Validated request and response schemas for the public API."""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class SourceCitation(BaseModel):
    document: str
    document_id: str
    page_number: int
    chunk_id: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    verified: bool


class MessageResponse(BaseModel):
    message: str
