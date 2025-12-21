from fastapi import APIRouter, HTTPException
from models.student import StudentCreate, RecommendationResponse, StudentDetail
from services.student_service import StudentService

router = APIRouter(prefix="/api/v1", tags=["students"])

student_service = StudentService()

@router.post("/onboard", response_model=dict)
async def onboard_student(student: StudentCreate):
    """
    Onboard a new student to the system.
    Creates a Student node in Neo4j with auto-incremented id.
    """
    try:
        student_id = student_service.save_student(student)
        return {
            "message": "Student onboarded successfully",
            "student_id": student_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error onboarding student: {str(e)}")


@router.get("/recommend/people/{student_id}", response_model=RecommendationResponse)
async def recommend_people(student_id: int):
    """
    Get recommended students for a given student_id.
    Returns students who match on at least one attribute (OR logic).
    Includes a human-readable message listing all matched students.
    """
    try:
        recommendations = student_service.recommend_people(student_id)
        
        # Create human-readable message
        if not recommendations:
            message = "No matching students found in this platform."
        else:
            names = [rec.name for rec in recommendations]
            if len(names) == 1:
                message = f"{names[0]} is also in this platform."
            elif len(names) == 2:
                message = f"{names[0]} and {names[1]} are also in this platform."
            else:
                # Format: "Pragya, Siddharth, and Nabin are also in this platform"
                all_but_last = ", ".join(names[:-1])
                last_name = names[-1]
                message = f"{all_but_last}, and {last_name} are also in this platform."
        
        return RecommendationResponse(
            students=recommendations,
            message=message,
            total_matches=len(recommendations)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {str(e)}")


@router.post("/sync", response_model=dict)
async def sync_json_to_neo4j():
    """
    Manually sync all students from students.json to Neo4j database.
    Useful if you've manually added students to the JSON file.
    """
    try:
        student_service.sync_json_to_neo4j()
        return {
            "message": "Successfully synced students from JSON to Neo4j"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing students: {str(e)}")



@router.get("/students/{student_id}", response_model=StudentDetail)
async def get_student(student_id: int):
    """
    Get a single student's full details by id.
    """
    try:
        student = student_service.get_student_by_id(student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching student: {str(e)}")

