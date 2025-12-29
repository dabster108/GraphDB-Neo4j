from dotenv import load_dotenv
from graphdb import Neo4jConnection
import requests

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
                        You are an expert Neo4j Cypher developer.

                        Rules:
                        - Only return a single valid Cypher query.
                        - Do NOT add explanations, comments or markdown.
                        - Assume nodes: Student
                        - Assume relationships: KNOWS, FRIEND_OF, CLASSMATE_OF
                        - Use the following properties for Student nodes:
                            - name (string)
                            - address (optional string)
                            - college (optional string)
                            - board (optional string)
                            - stream (optional string)
                            - interests (optional list of strings)
                        - Preserve exact casing when matching by `name`: use exact equality (e.g. `s.name = "Aashish"`). Do NOT call `toLower()` on `name` values.
                        - For other text properties (address, college, board, stream, interests) use case-insensitive matching with `toLower()` (e.g. `toLower(s.address) = toLower("Kathmandu")` or `toLower(s.interests) CONTAINS toLower("fifa")`).
                        - Use `OPTIONAL MATCH` when relationships or optional properties are being queried, but ensure the query always ends with an appropriate `RETURN` clause.
                        - When returning counts use an alias like `AS num_students`.
                        - When returning names or nodes, return clear fields (e.g. `RETURN s.name` or `RETURN s`).
                        - Avoid using regex `=~` unless explicitly needed; prefer `toLower() = toLower(...)` or `CONTAINS` for partial matches.

                        Question:
                        {question}
                        """,
            "stream": False
        }
        # Send the HTTP POST request to Ollama
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        response.raise_for_status()  # Raise an error for HTTP issues
        data = response.json()
        return data.get("response", "I'm sorry, I couldn't generate a Cypher query.")
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
                if isinstance(value, (int, float)):
                    return f"There are {value} students in your database."
            for k, v in first.items():
                if isinstance(v, (int, float)) or "count" in k.lower():
                    return f"There are {v} students in your database."

        # Otherwise, call the LLM for a concise conversational explanation
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

            # Send the raw results to the LLM and print a single conversational reply
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
