import sys
import os
import json
# Add src directory to path to import graphdb
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from graphdb import Neo4jConnection
from typing import List, Optional
from models.student import StudentCreate, StudentResponse, StudentDetail


class StudentService:
    def __init__(self):
        self.db = Neo4jConnection()
        self.db.connect()
        # Path to students.json file
        self.resources_dir = os.path.join(os.path.dirname(__file__), '../resources')
        self.students_json_path = os.path.join(self.resources_dir, 'students.json')
        
        # Ensure resources directory exists
        os.makedirs(self.resources_dir, exist_ok=True)
        
        # Sync JSON data to Neo4j on initialization
        self._sync_json_to_neo4j()

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

    def save_student(self, student: StudentCreate) -> int:
        """
        Save a student to Neo4j and students.json file.
        Returns the auto-incremented student id.
        """
        with self.db.driver.session(database=self.db.database) as session:
            # Get the next available student id
            result = session.run(
                "MATCH (s:Student) RETURN MAX(s.id) as max_id"
            )
            record = result.single()
            next_id = (record["max_id"] or 0) + 1

            # Create the student node in Neo4j
            session.run(
                """
                CREATE (s:Student {
                    id: $id,
                    name: $name,
                    address: $address,
                    college: $college,
                    board: $board,
                    stream: $stream,
                    interests: $interests
                })
                RETURN s.id as id
                """,
                id=next_id,
                name=student.name,
                address=student.address,
                college=student.college,
                board=student.board,
                stream=student.stream,
                interests=student.interests
            )

        # Save to JSON file
        self._save_to_json(next_id, student)
        
        return next_id

    def _save_to_json(self, student_id: int, student: StudentCreate):
        students = []
        if os.path.exists(self.students_json_path):
            try:
                with open(self.students_json_path, 'r', encoding='utf-8') as f:
                    students = json.load(f)
            except (json.JSONDecodeError, IOError):
                students = []
        
        # Create student data dictionary
        student_data = {
            "id": student_id,
            "name": student.name,
            "address": student.address,
            "college": student.college,
            "board": student.board,
            "stream": student.stream,
            "interests": student.interests
        }
        
       
        existing_index = next((i for i, s in enumerate(students) if s.get("id") == student_id), None)
        if existing_index is not None:
            students[existing_index] = student_data
        else:
            students.append(student_data)
        
        with open(self.students_json_path, 'w', encoding='utf-8') as f:
            json.dump(students, f, indent=2, ensure_ascii=False)

    def _sync_json_to_neo4j(self):
        """
        Sync all students from students.json to Neo4j database.
        This ensures that any manually added students in JSON are also in Neo4j.
        """
        if not os.path.exists(self.students_json_path):
            return
        
        try:
            with open(self.students_json_path, 'r', encoding='utf-8') as f:
                students = json.load(f)
        except (json.JSONDecodeError, IOError):
            return
        
        with self.db.driver.session(database=self.db.database) as session:
            for student_data in students:
                # Check if student already exists in Neo4j
                result = session.run(
                    "MATCH (s:Student {id: $id}) RETURN s.id as id",
                    id=student_data.get("id")
                )
                existing = result.single()
                
                # Only create if it doesn't exist
                if not existing:
                    session.run(
                        """
                        CREATE (s:Student {
                            id: $id,
                            name: $name,
                            address: $address,
                            college: $college,
                            board: $board,
                            stream: $stream,
                            interests: $interests
                        })
                        """,
                        id=student_data.get("id"),
                        name=student_data.get("name"),
                        address=student_data.get("address"),
                        college=student_data.get("college"),
                        board=student_data.get("board"),
                        stream=student_data.get("stream"),
                        interests=student_data.get("interests", [])
                    )

    def sync_json_to_neo4j(self):
        """
        Public method to sync JSON to Neo4j (can be called from routes).
        """
        self._sync_json_to_neo4j()

    def get_student_by_id(self, student_id: int) -> Optional[StudentDetail]:
        """
        Retrieve a single student's full details by id.
        Returns a `StudentDetail` or `None` if not found.
        """
        with self.db.driver.session(database=self.db.database) as session:
            result = session.run(
                """
                MATCH (s:Student {id: $student_id})
                RETURN s.id as id, s.name as name, s.address as address,
                       s.college as college, s.board as board, s.stream as stream,
                       s.interests as interests
                """,
                student_id=student_id
            )
            record = result.single()

            if not record:
                # Try syncing from JSON then retry
                self._sync_json_to_neo4j()
                result = session.run(
                    """
                    MATCH (s:Student {id: $student_id})
                    RETURN s.id as id, s.name as name, s.address as address,
                           s.college as college, s.board as board, s.stream as stream,
                           s.interests as interests
                    """,
                    student_id=student_id
                )
                record = result.single()

            if not record:
                return None

            return StudentDetail(
                id=record["id"],
                name=record["name"],
                address=record.get("address"),
                college=record.get("college"),
                board=record.get("board"),
                stream=record.get("stream"),
                interests=record.get("interests") or []
            )

    def recommend_people(self, student_id: int) -> List[StudentResponse]:
        """
        Recommend students based on OR logic - match if ANY attribute matches.
        Returns list of recommended students with matched fields.
        """
        with self.db.driver.session(database=self.db.database) as session:
            # First, check if student exists
            current_student_result = session.run(
                """
                MATCH (s:Student {id: $student_id})
                RETURN s.board as board, s.stream as stream, s.college as college,
                       s.address as address, s.interests as interests
                """,
                student_id=student_id
            )
            current_record = current_student_result.single()
            
            if not current_record:
                # Student not found in Neo4j - try syncing from JSON first
                self._sync_json_to_neo4j()
                # Try again after sync
                current_student_result = session.run(
                    """
                    MATCH (s:Student {id: $student_id})
                    RETURN s.board as board, s.stream as stream, s.college as college,
                           s.address as address, s.interests as interests
                    """,
                    student_id=student_id
                )
                current_record = current_student_result.single()
                if not current_record:
                    return []

            current_board = current_record["board"]
            current_stream = current_record["stream"]
            current_college = current_record["college"]
            current_address = current_record["address"]
            current_interests = current_record["interests"] or []


            result = session.run(
                """
                MATCH (s:Student)
                WHERE s.id <> $student_id
                RETURN s.id as id, s.name as name, s.board as board, 
                       s.stream as stream, s.college as college,
                       s.address as address, s.interests as interests
                """,
                student_id=student_id
            )

            recommendations = []
            for record in result:
                matched_fields = []
                same_address = False
                matching_interests_list = []
                
                # Check board match
                if record["board"] == current_board:
                    matched_fields.append("board")
                
                # Check stream match
                if record["stream"] == current_stream:
                    matched_fields.append("stream")
                
                # Check college match
                if record["college"] == current_college:
                    matched_fields.append("college")
                
                # Check address match (same location)
                if record["address"] == current_address:
                    matched_fields.append("address")
                    same_address = True
                
                # Check interests match (find common interests)
                other_interests = record["interests"] or []
                matching_interests_list = [interest for interest in other_interests if interest in current_interests]
                if matching_interests_list:
                    matched_fields.append("interests")

                # Only add if at least one field matched (OR logic)
                if matched_fields:
                    recommendations.append(StudentResponse(
                        id=record["id"],
                        name=record["name"],
                        address=record["address"],
                        matched_on=matched_fields,
                        matching_interests=matching_interests_list if matching_interests_list else None,
                        same_address=same_address
                    ))

            return recommendations

