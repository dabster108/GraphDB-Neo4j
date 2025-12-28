from fastapi import FastAPI
import sys
import os
import threading
import subprocess
import sys as _sys
import os as _os

# Add fastapi directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../fastapi'))

from routes.student_routes import router

app = FastAPI(
    title="Student Onboarding and Recommendation API",
    description="API for student onboarding and people recommendation using Neo4j",
    version="1.0.0"
)

# Include routers
app.include_router(router)



@app.on_event("startup")
async def startup_backfill():
    # Always run backfill on startup
    def _backfill():
        script = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '../fastapi/services/create_relationships.py'))
        try:
            subprocess.run([_sys.executable, script], check=False)
        except Exception:
            pass

    threading.Thread(target=_backfill, daemon=True).start()


@app.get("/")
async def root():
    return {
        "message": "Student Onboarding and Recommendation API",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
