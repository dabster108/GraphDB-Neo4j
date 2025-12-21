from pydantic import BaseModel
from typing import List, Optional


class StudentCreate(BaseModel):
    name: str
    address: str
    college: str
    board: str
    stream: str
    interests: List[str]


class StudentResponse(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    matched_on: List[str]
    matching_interests: Optional[List[str]] = None
    same_address: bool = False


class RecommendationResponse(BaseModel):
    students: List[StudentResponse]
    message: str
    total_matches: int


class StudentDetail(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    college: Optional[str] = None
    board: Optional[str] = None
    stream: Optional[str] = None
    interests: Optional[List[str]] = None

