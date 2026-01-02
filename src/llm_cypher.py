from dotenv import load_dotenv
from graphdb import Neo4jConnection
import requests
import re
from rapidfuzz import fuzz, process

# Load environment variables
load_dotenv()

# Initialize Neo4j connection
neo4j_conn = Neo4jConnection()
neo4j_conn.connect()


def get_all_student_names() -> list:
    try:
        with neo4j_conn.driver.session(database=neo4j_conn.database) as session:
            result = session.run("MATCH (s:Student) RETURN s.name as name")
            return [record["name"] for record in result if record["name"]]
    except Exception as e:
        print(f"Error fetching student names: {e}")
        return []


def fuzzy_match_student_name(query_name: str, threshold: int = 80) -> str:
    all_names = get_all_student_names()
    if not all_names:
        return query_name
    
    result = process.extractOne(query_name.lower(), [n.lower() for n in all_names], scorer=fuzz.ratio)
    
    if result and result[1] >= threshold:
        matched_index = [n.lower() for n in all_names].index(result[0])
        matched_name = all_names[matched_index]
        print(f"Fuzzy match: '{query_name}' → '{matched_name}' (score: {result[1]})")
        return matched_name
    
    return query_name


def preprocess_question_with_fuzzy_matching(question: str) -> str:

    words = question.split()
    
    corrected_words = []
    for word in words:
        clean_word = re.sub(r'[^\w\s]', '', word)
        if len(clean_word) >= 3 and clean_word.lower() not in ['who', 'what', 'where', 'when', 'why', 'how', 'the', 'and', 'are', 'can', 'between', 'about', 'student', 'students', 'connection', 'relationship']:
            matched_name = fuzzy_match_student_name(clean_word, threshold=75)
            if matched_name != clean_word:
                corrected_words.append(word.replace(clean_word, matched_name))
            else:
                corrected_words.append(word)
        else:
            corrected_words.append(word)
    
    return ' '.join(corrected_words)


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

Absolute instructions (do not change behavior elsewhere in the code):
- Only output one Cypher query. No comments, no prose, no markdown.
- Student names are stored in lowercase. Always compare names case-insensitively: prefer `toLower(s.name) = toLower("name")` or use a lowercase literal in map patterns.
- For other textual properties (`college`, `board`, `stream`), case-insensitive comparison is acceptable.
- Always bind relationship variables when referencing `type(r)` or relationship properties (e.g., -[r:TYPE]-).
- Do not invent relationship types; when asked about relationships prefer path-based discovery that returns `type(rel)` and `properties(rel)`.

Intent handling:
- If the input is a greeting or small-talk (e.g., "hi", "hello", "hey", "yo", "how are you", "thanks"), do NOT produce any Cypher. Output exactly `CHAT`.
- If the input asks general capability/meta (e.g., "what can you do", "why need of query", "help", "can we chat", "tell me about yourself"), output exactly `CHAT`.
- If the input clearly refers to the student database (mentions student-related fields, IDs, relationships) or includes one/two personal names, generate a Cypher query.
- If the user's input contains a single personal name (single token like "dikshanta" or a multi-word name like "John Doe"), treat it as a request about a `Student` node and produce the SINGLE-STUDENT DETAILS QUERY below.
- If the user's input contains exactly two distinct personal names, treat it as a two-student relationship question and produce the TWO-NAME RELATIONSHIP QUERY pattern below — match names case-insensitively.

Two-name relationship pattern (case-insensitive):
MATCH (a:Student), (b:Student)
WHERE toLower(a.name) = toLower("FirstStudentName") AND toLower(b.name) = toLower("SecondStudentName")
OPTIONAL MATCH p = (a)-[r]-(b)
RETURN a AS a, b AS b,
       [rel IN relationships(p) | type(rel)] AS rel_types,
       [rel IN relationships(p) | properties(rel)] AS rel_props,
       a.college = b.college AS same_college,
       a.board = b.board AS same_board,
       a.stream = b.stream AS same_stream,
       [x IN a.interests WHERE x IN b.interests] AS common_interests
LIMIT 25;

Single-student details pattern (case-insensitive):
MATCH (s:Student)
WHERE toLower(s.name) = toLower("StudentName")
RETURN s AS student, s.name AS name, s.college AS college, s.board AS board, s.stream AS stream, s.interests AS interests, s.address AS address
LIMIT 1;

Examples (authoritative):
Q: who is dikshanta?
A: (use single-student details pattern with name case-insensitive match "dikshanta")

Q: dikshanta
A: (use single-student details pattern with name case-insensitive match "dikshanta")

Q: what is the connection between Umesh and Rohan
A: (use two-name relationship pattern with names "Umesh" and "Rohan" using case-insensitive matching)

Q: hi
A: CHAT

Q: hello
A: CHAT

Q: what can you do?
A: CHAT

Q: why need of query
A: CHAT

Fallback rule:
- If the input is not a single-name or two-name detected case, produce the most concise, syntactically-correct Cypher that answers the natural-language question while respecting the rules above. If the input is casual chat, return `CHAT`.

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
        
        # Strip markdown code blocks (```, ```cypher, etc.)
        def strip_markdown_code_blocks(text: str) -> str:
            # Remove opening code fence (```cypher, ```sql, or just ```)
            text = re.sub(r'^```(?:cypher|sql)?\s*\n?', '', text.strip(), flags=re.MULTILINE)
            # Remove closing code fence
            text = re.sub(r'\n?```\s*$', '', text.strip(), flags=re.MULTILINE)
            return text.strip()
        
        raw = strip_markdown_code_blocks(raw)
        
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

        # Ensure case-insensitive matching for Student name comparisons and lowercase literals
        def enforce_case_insensitive_name_matching(q: str) -> str:
            # s.name = "Literal" -> toLower(s.name) = toLower("literal")
            def eq_repl(m):
                prop = m.group(1)
                quote = m.group(2)
                lit = m.group(3)
                return f"toLower({prop}) = toLower({quote}{lit.lower()}{quote})"
            q = re.sub(r"([A-Za-z_][A-Za-z0-9_]*\.[Nn]ame)\s*=\s*(['\"])(.+?)\2", eq_repl, q)

            # MATCH (s:Student {name: "Literal"}) -> lower the literal only
            def map_repl(m):
                prefix = m.group(1)
                quote = m.group(2)
                lit = m.group(3)
                return f"{prefix}{quote}{lit.lower()}{quote}"
            q = re.sub(r"(\{[^}]*\bname\s*:\s*)(['\"])(.+?)\2", map_repl, q)
            return q

        fixed = enforce_case_insensitive_name_matching(fixed)

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

        return fixed2
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
        payload = {
            "model": "llama3.1:8b",
            "prompt": f"""
You are a friendly chatbot.

Rules:
- If the user's message is a greeting like "hi", "hello", or "hey", respond exactly:
  Hi there! How's your day going so far? Is there something I can help you with or would you like to just have a friendly conversation?
- Otherwise, reply naturally, be concise (one or two sentences), and offer help.

User:
{question}

Reply:
""",
            "stream": False
        }
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "I'm sorry, I couldn't generate a response.")
    except Exception as e:
        print(f"Error in normal_chat: {e}")
        return "I'm sorry, but I'm having trouble generating a response right now."





def main():
    print("Connected to Neo4j database: neo4j!")
    print("Welcome to the Neo4j Chatbot!")
    print("Ask about student relationships or have a casual chat (type 'exit' to quit).")
    print("🔍 Fuzzy search enabled - typos in names will be auto-corrected!\n")

    while True:
        question = input("\nYour Question: ")
        if question.lower() == "exit":
            print("Goodbye!")
            break
        
        # Preprocess the question with fuzzy name matching
        corrected_question = preprocess_question_with_fuzzy_matching(question)
        if corrected_question != question:
            print(f"💡 Understood as: {corrected_question}")
        
        # Always attempt to generate a Cypher query first (database-first behavior).
        print("\nUnderstanding your question...")

        cypher_query = generate_cypher_query(corrected_question)

        # Heuristic: treat the generated text as Cypher if it contains a MATCH keyword (case-insensitive).
        if isinstance(cypher_query, str) and re.search(r"\bMATCH\b", cypher_query, re.IGNORECASE):
            print(f"\nGenerated Cypher Query:\n{cypher_query}")
            print("\nExecuting query...")
            result = execute_cypher_query(cypher_query)
            # Send the raw results to the LLM (or local analyzer) and print a single conversational reply
            llm_reply = explain_result_with_llm(question, result)
            print(f"\nChatbot: {llm_reply}")
        else:
            # Fallback to normal chat when the generator did not produce a Cypher query
            print("\nChatbot: Thinking...")
            reply = normal_chat(question)
            print(f"Chatbot: {reply}")


if __name__ == "__main__":
    main()

# Close the Neo4j connection when the script ends
neo4j_conn.close()