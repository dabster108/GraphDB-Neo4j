# Graph database stores data as nodes 
# Relationships matter more than the node 
# Used in Social Networks, Recommendation System 
# Nodes -> Object 
# Relationship -> How two nodes are connected 
# Properties are key-value pair used for storing data on nodes 
# Properties can hold different data such as number, string, boolean 

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

class Neo4jConnection:
    def __init__(self, database="neo4j"):
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = database
        self.driver = None

    def connect(self):
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        print(f"Connected to Neo4j database: {self.database}!")

    def close(self):
        if self.driver:
            self.driver.close()
            print("Connection closed.")

    def create_user(self, name, age):
        with self.driver.session(database=self.database) as session:
            result = session.run(
                "CREATE (u:User {name: $name, age: $age}) RETURN u",
                name=name,
                age=age
            )
            record = result.single()
            print(f"Created user: {record['u']['name']}, age: {record['u']['age']}")
