from dotenv import load_dotenv
from graphdb import Neo4jConnection
import requests
import re

# Load environment variables
load_dotenv()

# Initialize Neo4j connection
neo4j_conn = Neo4jConnection()
neo4j_conn.connect()


def generate_cypher_query(question: str) -> str:
    """
    Use a local Ollama model to generate a Cypher query from a natural language question.
    """
    try:
        # Define the request payload for Ollama
        payload = {
            "model": "llama3.1:8b",
            "prompt": f"""
You are an expert Neo4j Cypher developer and graph data modeler. Produce a single valid Cypher query only, no explanation or extra text.

Requirements and rules:
- Only return one Cypher query. Do NOT add comments, explanations, or markdown.
- Preserve exact casing for Student `name` property: match `name` by exact equality (e.g. `s.name = "Shristi"`). Do NOT wrap literal names with `toLower()`.
- If comparing other text properties (college, board, stream), case-insensitive comparisons are acceptable.
- Always bind relationship variables if you use `type(r)` or relationship properties (e.g. `-[r:TYPE]-`).
- Avoid guessing specific relationship types when the user asks "relationship between X and Y"; instead prefer a path/property comparison pattern that returns relationship types and property-based comparisons.

If the user asks a question of the form "relationship between <NameA> and <NameB>", produce a safe, deterministic query that:
- matches the two students by exact `name` equality
- OPTIONAL MATCHes any direct relationship or short path between them
- RETURNS the two nodes, the list of relationship types on any path, relationship properties, and simple boolean or list comparisons for `college`, `board`, `stream`, and `interests`.

Example of the expected pattern to return (follow this format when applicable):
MATCH (a:Student {{name: "NameA"}}), (b:Student {{name: "NameB"}})
OPTIONAL MATCH p = (a)-[r]-(b)
RETURN a AS a, b AS b,
       [rel IN relationships(p) | type(rel)] AS rel_types,
       [rel IN relationships(p) | properties(rel)] AS rel_props,
       a.college = b.college AS same_college,
       a.board = b.board AS same_board,
       a.stream = b.stream AS same_stream,
       [x IN a.interests WHERE x IN b.interests] AS common_interests
LIMIT 25;

If the question is not a direct two-name relationship question, produce the most appropriate, concise Cypher that answers the user's natural-language query. Always ensure the query is syntactically correct.

Special case — user requests "details" about a student:
- If the user asks "details about <Name>" or similar, return a concise query that selects the student by exact `name` and returns core properties.
- Example pattern to use for details requests:
MATCH (s:Student {{name: "Name"}})
RETURN s AS student, s.name AS name, s.college AS college, s.board AS board, s.stream AS stream, s.interests AS interests, s.address AS address
LIMIT 1;

Do NOT include relationships in the details query unless the user explicitly asks for connections/relationships.

Question:
{question}
""",
            "stream": False
        }
        # Send the HTTP POST request to Ollama
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        response.raise_for_status()  # Raise an error for HTTP issues
        data = response.json()
        raw = data.get("response", "I'm sorry, I couldn't generate a Cypher query.")
        # Sanitize and fix common Cypher syntax mistakes emitted by LLMs
        def sanitize_cypher(q: str) -> str:
            # Fix patterns where relationships are accidentally wrapped in parentheses like -([r]-> or -([r])- etc.
            q = re.sub(r"-\(\s*(\[[^\]]+\])\s*->", r"-\1->", q)
            q = re.sub(r"<-\(\s*(\[[^\]]+\])\s*\)-", r"<-\1-", q)
            q = re.sub(r"-\(\s*(\[[^\]]+\])\s*\)-", r"-\1-", q)
            # Remove empty parentheses accidentally placed around relationship variables: ( [r] ) -> [r]
            q = re.sub(r"\(\s*(\[[^\]]+\])\s*\)", r"\1", q)
            # Normalize multiple spaces
            q = re.sub(r"\s+", " ", q).strip()
            return q

        fixed = sanitize_cypher(raw)

        # Remove toLower(...) wrappers that the LLM may have added around literal names
        # and around `.name` property access — user wants exact-name matching preserved.
        # Only rewrite toLower(X.name) -> X.name and toLower("Literal") -> "Literal" (or single-quoted).
        def preserve_literal_names(q: str) -> str:
            # toLower(s.name) -> s.name (only for `.name` accessors)
            q = re.sub(r"toLower\(\s*([A-Za-z_][A-Za-z0-9_]*\.[Nn]ame)\s*\)", r"\1", q)
            # toLower("Some Name") or toLower('Some Name') -> "Some Name" (preserve original quoting)
            q = re.sub(r"toLower\(\s*(['\"])(.*?)\1\s*\)", r"\1\2\1", q)
            return q

        fixed = preserve_literal_names(fixed)

        # Fix incorrect size[list comprehension] usage (should be size([ ... ])).
        def fix_size_brackets(q: str) -> str:
            # Replace size[<expr>] with size([<expr>])
            return re.sub(r"size\s*\[\s*([^\]]+?)\s*\]", r"size([\1])", q)

        fixed = fix_size_brackets(fixed)

        # Further fix: if the query returns relationship types via type(r) but r wasn't bound,
        # try to bind r to the first relationship pattern, or if the relationship is variable-length,
        # convert the MATCH into a path `p` and return the list of relationship types.
        def fix_unbound_relationship_types(q: str) -> str:
            if "type(" not in q:
                return q
            # If r is already bound, nothing to do
            if re.search(r"\[\s*r\b", q):
                return q

            q_work = q
            # Try to bind `r` to the first occurrence of an anonymous relationship pattern
            # Replace first '<-[:' or '-[:' occurrence
            if "<-[:" in q_work:
                q_work = q_work.replace("<-[:", "<-[r:", 1)
            elif "-[:" in q_work:
                q_work = q_work.replace("-[:", "-[r:", 1)

            # If the bound relationship is variable-length (contains '*'), use path approach
            if re.search(r"\[r:[^\]]*\*", q_work):
                # Ensure MATCH uses a path variable `p =` for the first MATCH occurrence
                q_work = re.sub(r"\bMATCH\s+", "MATCH p = ", q_work, count=1)
                # Replace occurrences of `type(r)` with mapping over relationships(p)
                q_work = re.sub(r"type\(\s*r\s*\)\s+AS\s+(\w+)", r"[rel IN relationships(p) | type(rel)] AS \1", q_work)
                q_work = re.sub(r"type\(\s*r\s*\)", "[rel IN relationships(p) | type(rel)]", q_work)
            else:
                # For simple fixed-length relationship, ensure `type(r)` returns single rel
                # (we already injected r into pattern above)
                pass

            return q_work

        fixed2 = fix_unbound_relationship_types(fixed)

        # Preserve exact casing of names as provided by the user in the question.
        def preserve_user_literal_case(q: str, question_text: str) -> str:
            # Find all double- or single-quoted literals in the query
            def replace_match(m):
                quote = m.group(1)
                lit = m.group(2)
                # Search for the literal text in the question (case-insensitive)
                try:
                    pat = re.compile(re.escape(lit), flags=re.IGNORECASE)
                    mm = pat.search(question_text)
                    if mm:
                        user_exact = question_text[mm.start():mm.end()]
                        return f"{quote}{user_exact}{quote}"
                except Exception:
                    pass
                return m.group(0)

            return re.sub(r"(['\"])(.+?)\1", replace_match, q)

        return preserve_user_literal_case(fixed2, question)
    except Exception as e:
        print(f"Error in generate_cypher_query: {e}")
        return "I'm sorry, but I couldn't generate a Cypher query."


def execute_cypher_query(query: str) -> list:
    """
    Execute the Cypher query on the Neo4j database using Neo4jConnection and return the result.
    """
    results = []
    try:
        print(f"Executing Cypher Query: {query}")  # Log the query being executed
        with neo4j_conn.driver.session(database=neo4j_conn.database) as session:
            result = session.run(query)
            results = [record.data() for record in result]
        print(f"Query Results: {results}")  # Log the results for debugging
    except Exception as e:
        print(f"Error executing query: {e}")
    return results


def explain_result(question: str, result: list) -> str:
    """
    Explain the result of the Cypher query in natural language.

    - Handle empty results.
    - Generate detailed and conversational explanations for the results.
    """
    if not result:
        return "I'm sorry, but I couldn't find any students matching your query in the database."

    # Check if the result contains a count
    if len(result) == 1 and "COUNT(s)" in result[0]:
        count = result[0]["COUNT(s)"]
        return f"There are {count} students matching your query in the database."

    # Handle multiple student records
    explanations = []
    for record in result:
        if "s" in record:
            student = record["s"]
            details = []
            if "name" in student:
                details.append(f"Name: {student['name']}")
            if "address" in student:
                details.append(f"Address: {student['address']}")
            if "college" in student:
                details.append(f"College: {student['college']}")
            if "board" in student:
                details.append(f"Board: {student['board']}")
            if "stream" in student:
                details.append(f"Stream: {student['stream']}")
            if "interests" in student:
                interests = ", ".join(student['interests'])
                details.append(f"Interests: {interests}")

            explanations.append("\n".join(details))

    # Combine all student details into a conversational response
    response = "I found the following students matching your query:\n\n"
    response += "\n\n".join(explanations)
    return response


def explain_result_with_llm(question: str, result: list) -> str:
    """
    Use the LLM to generate a conversational explanation of the query results.
    """
    try:
        # Handle empty results quickly
        if not result:
            return "No students found matching your query."

        # If result is a single-record count, return concise local reply
        if len(result) == 1:
            first = result[0]
            if len(first) == 1:
                key, value = next(iter(first.items()))
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return f"There are {value} students in your database."
            for k, v in first.items():
                # treat numeric counts only (exclude booleans which are subclasses of int)
                if (isinstance(v, (int, float)) and not isinstance(v, bool)) or "count" in k.lower():
                    # only return a numeric count; if the value is boolean, skip
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        return f"There are {v} students in your database."

        # Call the LLM for a concise conversational explanation
        # Format the result compactly
        result_str = repr(result)
        payload = {
            "model": "llama3.1:8b",
            "prompt": f"""
You are a helpful assistant. Produce a concise, conversational reply (one or two sentences) for a user based on the question and the database results.

Instructions:
- Keep the reply short and natural (like a chat reply).
- If the results list student objects, mention up to 5 names or summarize if many.
- If shared interests are present, list the common interests succinctly.
- Do NOT include JSON, code blocks, or internal keys; only plain text.

Question:
{question}

Database Results:
{result_str}

Reply:
""",
            "stream": False
        }
        # Send the HTTP POST request to Ollama
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "I'm sorry, I couldn't generate an explanation.")
    except Exception as e:
        print(f"Error in explain_result_with_llm: {e}")
        return "I'm sorry, but I couldn't generate an explanation."


def normal_chat(question: str) -> str:
    """
    Handle normal chatbot conversations using a local Ollama model.
    """
    try:
        # Define the request payload for Ollama
        payload = {
            "model": "llama3.1:8b",
            "prompt": f"You are a friendly chatbot. Answer this: {question}",
            "stream": False
        }
        # Send the HTTP POST request to Ollama
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        response.raise_for_status()  # Raise an error for HTTP issues
        data = response.json()
        return data.get("response", "I'm sorry, I couldn't generate a response.")
    except Exception as e:
        print(f"Error in normal_chat: {e}")
        return "I'm sorry, but I'm having trouble generating a response right now."





def main():
    print("Connected to Neo4j database: neo4j!")
    print("Welcome to the Neo4j Chatbot!")
    print("Ask about student relationships or have a casual chat (type 'exit' to quit).")

    while True:
        question = input("\nYour Question: ")
        if question.lower() == "exit":
            print("Goodbye!")
            break

        # Check if the question is database-related
        if "student" in question.lower() or "relationship" in question.lower() or "database" in question.lower():
            print("\nUnderstanding your question...")

            cypher_query = generate_cypher_query(question)
            print(f"\nGenerated Cypher Query:\n{cypher_query}")

            print("\nExecuting query...")
            result = execute_cypher_query(cypher_query)
            # Send the raw results to the LLM (or local analyzer) and print a single conversational reply
            llm_reply = explain_result_with_llm(question, result)
            print(f"\nChatbot: {llm_reply}")
        else:
            # Handle normal chat
            print("\nChatbot: Thinking...")
            reply = normal_chat(question)
            print(f"Chatbot: {reply}")


if __name__ == "__main__":
    main()

# Close the Neo4j connection when the script ends
neo4j_conn.close()
