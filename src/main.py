from graphdb import Neo4jConnection
#poc 
def main():
    # Create connection instance
    db = Neo4jConnection()
    
    try:
        db.connect()
        db.create_user("Dikshanta", 25)
        db.create_user("Jijash", 30)
        
        print("\nTwo users created successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    main()






