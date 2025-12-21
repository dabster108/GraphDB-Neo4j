import sys
import os
import argparse

# ensure src is on path to import graphdb
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
from graphdb import Neo4jConnection


def _connect():
    conn = Neo4jConnection()
    conn.connect()
    return conn


def create_same_college():
    q = """
    MATCH (a:Student), (b:Student)
    WHERE a.id < b.id
      AND a.college IS NOT NULL
      AND a.college = b.college
    MERGE (a)-[:SAME_COLLEGE]->(b)
    """
    conn = _connect()
    try:
        with conn.driver.session(database=conn.database) as session:
            session.run(q)
    finally:
        conn.close()


def create_same_board():
    q = """
    MATCH (a:Student), (b:Student)
    WHERE a.id < b.id
      AND a.board IS NOT NULL
      AND a.board = b.board
    MERGE (a)-[:SAME_BOARD]->(b)
    """
    conn = _connect()
    try:
        with conn.driver.session(database=conn.database) as session:
            session.run(q)
    finally:
        conn.close()


def create_same_stream():
    q = """
    MATCH (a:Student), (b:Student)
    WHERE a.id < b.id
      AND a.stream IS NOT NULL
      AND a.stream = b.stream
    MERGE (a)-[:SAME_STREAM]->(b)
    """
    conn = _connect()
    try:
        with conn.driver.session(database=conn.database) as session:
            session.run(q)
    finally:
        conn.close()


def create_nearby():
    q = """
    MATCH (a:Student), (b:Student)
    WHERE a.id < b.id
      AND a.address IS NOT NULL
      AND a.address = b.address
    MERGE (a)-[:NEARBY]->(b)
    """
    conn = _connect()
    try:
        with conn.driver.session(database=conn.database) as session:
            session.run(q)
    finally:
        conn.close()


def create_shares_interest():
    q = """
    MATCH (a:Student), (b:Student)
    WHERE a.id < b.id
      AND any(x IN a.interests WHERE x IN b.interests)
    MERGE (a)-[r:SHARES_INTEREST]->(b)
    SET r.common = [x IN a.interests WHERE x IN b.interests]
    """
    conn = _connect()
    try:
        with conn.driver.session(database=conn.database) as session:
            session.run(q)
    finally:
        conn.close()


def run_all(create_board=True, create_college=True, create_stream=True, create_address=True, create_interest=True):
    if create_college:
        create_same_college()
    if create_board:
        create_same_board()
    if create_stream:
        create_same_stream()
    if create_address:
        create_nearby()
    if create_interest:
        create_shares_interest()


def _cli():
    parser = argparse.ArgumentParser(description='Create relationships between Student nodes based on shared attributes')
    parser.add_argument('--no-board', action='store_true', help='Skip creating SAME_BOARD relationships')
    parser.add_argument('--no-college', action='store_true', help='Skip creating SAME_COLLEGE relationships')
    parser.add_argument('--no-stream', action='store_true', help='Skip creating SAME_STREAM relationships')
    parser.add_argument('--no-address', action='store_true', help='Skip creating NEARBY relationships')
    parser.add_argument('--no-interest', action='store_true', help='Skip creating SHARES_INTEREST relationships')
    args = parser.parse_args()

    run_all(
        create_board=not args.no_board,
        create_college=not args.no_college,
        create_stream=not args.no_stream,
        create_address=not args.no_address,
        create_interest=not args.no_interest,
    )


if __name__ == '__main__':
    _cli()
