import sys
import os
# Add src directory to path to import graphdb
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from graphdb import Neo4jConnection
from typing import List, Optional
from models.student import StudentCreate, StudentResponse, StudentDetail
from rapidfuzz import fuzz


class StudentService:
    def __init__(self):
        self.db = Neo4jConnection()
        self.db.connect()

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

    def save_student(self, student: StudentCreate) -> int:
        """
        Save a student to Neo4j.
        Returns the auto-incremented student id.
        """
        name = student.name
        address = student.address
        college = student.college
        board = student.board
        stream = student.stream
        interests = student.interests or []

        with self.db.driver.session(database=self.db.database) as session:
            result = session.run(
                "MATCH (s:Student) RETURN MAX(s.id) as max_id"
            )
            record = result.single()
            next_id = (record["max_id"] or 0) + 1

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
                name=name,
                address=address,
                college=college,
                board=board,
                stream=stream,
                interests=interests
            )

            session.run(
                """
                MATCH (s:Student {id: $id}), (o:Student)
                WHERE o.id <> $id AND s.college IS NOT NULL AND s.college = o.college
                MERGE (s)-[:SAME_COLLEGE]->(o)
                """,
                id=next_id
            )

            session.run(
                """
                MATCH (s:Student {id: $id}), (o:Student)
                WHERE o.id <> $id AND s.board IS NOT NULL AND s.board = o.board
                MERGE (s)-[:SAME_BOARD]->(o)
                """,
                id=next_id
            )

            session.run(
                """
                MATCH (s:Student {id: $id}), (o:Student)
                WHERE o.id <> $id AND s.stream IS NOT NULL AND s.stream = o.stream
                MERGE (s)-[:SAME_STREAM]->(o)
                """,
                id=next_id
            )

            session.run(
                """
                MATCH (s:Student {id: $id}), (o:Student)
                WHERE o.id <> $id AND s.address IS NOT NULL AND s.address = o.address
                MERGE (s)-[:NEARBY]->(o)
                """,
                id=next_id
            )

            session.run(
                """
                MATCH (s:Student {id: $id}), (o:Student)
                WHERE o.id <> $id AND any(x IN s.interests WHERE x IN o.interests)
                MERGE (s)-[r:SHARES_INTEREST]->(o)
                SET r.common = [x IN s.interests WHERE x IN o.interests]
                """,
                id=next_id
            )

        return next_id

    def get_student_by_id(self, student_id: int) -> Optional[StudentDetail]:
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
                return None
            return StudentDetail(
                id=record["id"],
                name=record["name"],
                address=record.get("address"),
                college=record.get("college"),
                board=record.get("board"),
                stream=record.get("stream"),
                interests=record.get("interests") or [],
            )

    def recommend_people(self, student_id: int) -> List[StudentResponse]:
        """
        Recommend students based on OR logic - case/space-insensitive comparisons.
        """
        with self.db.driver.session(database=self.db.database) as session:
            exists = session.run(
                "MATCH (s:Student {id: $student_id}) RETURN s.id AS id",
                student_id=student_id,
            ).single()
            if not exists:
                return []

            q = """
            MATCH (s:Student {id: $student_id})
            MATCH (o:Student)
            WHERE o.id <> $student_id
            WITH s, o,
              (CASE WHEN toLower(trim(coalesce(o.board, ''))) = toLower(trim(coalesce(s.board, ''))) THEN 1 ELSE 0 END) AS bm,
              (CASE WHEN toLower(trim(coalesce(o.stream, ''))) = toLower(trim(coalesce(s.stream, ''))) THEN 1 ELSE 0 END) AS sm,
              (CASE WHEN toLower(trim(coalesce(o.college, ''))) = toLower(trim(coalesce(s.college, ''))) THEN 1 ELSE 0 END) AS cm,
              (CASE WHEN toLower(trim(coalesce(o.address, ''))) = toLower(trim(coalesce(s.address, ''))) THEN 1 ELSE 0 END) AS am,
              [x IN coalesce(o.interests, []) WHERE any(y IN coalesce(s.interests, []) WHERE toLower(trim(x)) = toLower(trim(y)))] AS matching_interests
            WITH o, bm, sm, cm, am, matching_interests, (bm + sm + cm + am + size(matching_interests)) AS score
            WHERE score > 0
            RETURN o.id AS id, o.name AS name, o.address AS address, o.interests AS interests,
                   bm AS board_match, sm AS stream_match, cm AS college_match, am AS address_match,
                   matching_interests AS matching_interests, score
            ORDER BY score DESC
            """

            result = session.run(q, student_id=student_id)
            recommendations: List[StudentResponse] = []
            for rec in result:
                matched_fields = []
                if rec["board_match"]:
                    matched_fields.append("board")
                if rec["stream_match"]:
                    matched_fields.append("stream")
                if rec["college_match"]:
                    matched_fields.append("college")
                if rec["address_match"]:
                    matched_fields.append("address")

                matching_interests = rec.get("matching_interests") or []
                if matching_interests:
                    matched_fields.append("interests")

                recommendations.append(StudentResponse(
                    id=rec["id"],
                    name=rec["name"],
                    address=rec.get("address"),
                    matched_on=matched_fields,
                    matching_interests=matching_interests if matching_interests else None,
                    same_address=bool(rec.get("address_match")),
                ))

            return recommendations

    def ping(self) -> bool:
        """Quick DB connectivity check."""
        try:
            with self.db.driver.session(database=self.db.database) as session:
                session.run("RETURN 1").single()
            return True
        except Exception:
            return False

    def sync_lowercase_students(self) -> int:
        """
        Lowercase all relevant fields for all Student nodes.
        Returns the number of student nodes processed.
        """
        with self.db.driver.session(database=self.db.database) as session:
            result = session.run(
                """
                MATCH (s:Student)
                SET s.name    = CASE WHEN s.name    IS NULL THEN NULL ELSE toLower(s.name)    END,
                    s.address = CASE WHEN s.address IS NULL THEN NULL ELSE toLower(s.address) END,
                    s.college = CASE WHEN s.college IS NULL THEN NULL ELSE toLower(s.college) END,
                    s.board   = CASE WHEN s.board   IS NULL THEN NULL ELSE toLower(s.board)   END,
                    s.stream  = CASE WHEN s.stream  IS NULL THEN NULL ELSE toLower(s.stream)  END,
                    s.interests = [x IN coalesce(s.interests, []) | toLower(x)]
                RETURN count(s) AS processed
                """
            )
            rec = result.single()
            return rec["processed"] if rec else 0
    
    def fuzzy_search_students(self, query: str, threshold: int = 70, limit: int = 10) -> List[StudentDetail]:
        """
        Fuzzy search for students by name.
        Args:
            query: The search query (e.g., 'dikshantass' or 'rebant')
            threshold: Minimum similarity score (0-100). Default is 70.
            limit: Maximum number of results to return. Default is 10.
        Returns:
            List of students matching the fuzzy search, sorted by similarity score.
        """
        query_lower = query.lower().strip()
        
        with self.db.driver.session(database=self.db.database) as session:
            # Get all students
            result = session.run(
                """
                MATCH (s:Student)
                RETURN s.id as id, s.name as name, s.address as address,
                       s.college as college, s.board as board, s.stream as stream,
                       s.interests as interests
                """
            )
            
            students_with_scores = []
            for record in result:
                student_name = record["name"] or ""
                score = fuzz.ratio(query_lower, student_name.lower())
                
                if score >= threshold:
                    students_with_scores.append({
                        "student": StudentDetail(
                            id=record["id"],
                            name=record["name"],
                            address=record.get("address"),
                            college=record.get("college"),
                            board=record.get("board"),
                            stream=record.get("stream"),
                            interests=record.get("interests") or [],
                        ),
                        "score": score
                    })
            
            # Sort by score descending and limit results
            students_with_scores.sort(key=lambda x: x["score"], reverse=True)
            return [item["student"] for item in students_with_scores[:limit]]

