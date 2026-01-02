# Graph Database Learning Project (Python)

This project is a simple starting point for learning about graph databases using Python.
It empowers simple relationship recommendation engine with fastapi as a backend

## What is a Graph Database?

A **graph database** is a type of database that uses graph structures with nodes (entities), edges (relationships), and properties (attributes) to represent and store data. Unlike traditional relational databases, graph databases are optimized for exploring and analyzing relationships between data points. They are especially useful for applications like social networks, recommendation engines, fraud detection, and network analysis.

### Example Concepts:

- **Nodes:** Represent entities (e.g., people, products, places)
- **Edges:** Represent relationships (e.g., friends with, bought, located at)
- **Properties:** Key-value pairs describing nodes or edges (e.g., name, age, date)

## What is `graphdb.py`?

The `src/graphdb.py` file is intended to contain the core logic for interacting with a graph database. As you learn, you can use this file to:

- Define how to create, update, and query nodes and edges
- Implement graph algorithms (like search, shortest path, etc.)
- Experiment with different ways to represent and manipulate graph data in Python

This file is your playground for building and understanding the basics of graph databases.

## What is Neo4j?

[Neo4j](https://neo4j.com/) is one of the most popular open-source graph database management systems. It is designed specifically for working with highly connected data and provides a powerful query language called Cypher. Neo4j is widely used in industry and academia for graph-based applications.

In this project, you can start by building your own simple graph structures in Python, and later explore how to connect to and use Neo4j for more advanced graph database features.

## Project Structure

- `src/graphdb.py`: Core logic for interacting with a graph database (to be implemented/expanded).
- `src/main.py`: Entry point for running and testing your graph database code.
- `src/llm_cypher.py`: Natural language to Cypher query conversion using Ollama LLM.
- `fastapi/`: FastAPI backend for the relationship recommendation engine.
- `pyproject.toml`: Project configuration and dependencies.

## Getting Started

1. **Clone the repository**
2. **Set up a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies** (if any):
   ```bash
   pip install -r requirements.txt
   # or use poetry if configured
   ```
4. **Set up Ollama** (for LLM-powered Cypher generation):
   - Install [Ollama](https://ollama.ai/)
   - Pull the required model:
   ```bash
   ollama pull llama3.1:8b
   ```
   - Start Ollama server (usually runs on `http://localhost:11434`)
5. **Configure Neo4j connection**:
   - Create a `.env` file in the project root with your Neo4j credentials:
   ```
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   NEO4J_DATABASE=neo4j
   ```
6. **Explore the code** in the `src/` folder and start experimenting!

## Features

### Natural Language to Cypher Query Generation

The project includes an LLM-powered feature (`llm_cypher.py`) that converts natural language questions into Cypher queries using Ollama:

- **Fuzzy Name Matching**: Automatically corrects student name typos using fuzzy string matching
- **Intelligent Query Generation**: Uses LLM (Llama 3.1:8b) to generate syntactically correct Cypher queries
- **Chat Detection**: Distinguishes between casual conversation and database queries
- **Relationship Discovery**: Finds connections between students including shared interests, colleges, boards, etc.
- **Query Sanitization**: Automatically fixes common Cypher syntax errors

#### Example Usage:

```python
from llm_cypher import generate_cypher_query, preprocess_question_with_fuzzy_matching

# Natural language query
question = "What is the connection between Dikshanta and Rohan?"

# Preprocess with fuzzy matching (corrects typos)
corrected_question = preprocess_question_with_fuzzy_matching(question)

# Generate Cypher query
cypher_query = generate_cypher_query(corrected_question)
```

#### Supported Query Types:

- Single student details: "Who is Dikshanta?" or just "Dikshanta"
- Student relationships: "What is the connection between Umesh and Rohan?"
- General queries: "Find all students from the same college"
- Chat detection: Handles greetings like "hi", "hello" without generating queries

## Learning Goals

- Understand the basics of graph data models (nodes, edges, properties)
- Learn how to represent and query graph data in Python
- Experiment with simple graph algorithms
- Use AI/LLM to generate Cypher queries from natural language

## Resources

- [Neo4j Graph Database](https://neo4j.com/developer/graph-database/)
- [Introduction to Graph Databases](https://www.geeksforgeeks.org/introduction-to-graph-databases/)
- [NetworkX Python Library](https://networkx.org/)
- [Ollama - Run LLMs locally](https://ollama.ai/)

## Next Steps

- Implement basic graph operations in `graphdb.py`
- Try out simple queries and algorithms
- Explore using libraries like NetworkX or connecting to Neo4j

---

# GraphDB-Neo4j
