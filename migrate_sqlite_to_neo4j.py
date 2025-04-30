import sqlite3
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

def main():
    # Load Neo4j connection settings from .env
    load_dotenv()
    uri      = os.getenv("NEO4J_URI")
    user     = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    # Open Neo4j driver
    driver = GraphDatabase.driver(uri, auth=(user, password))

    # 1) Migrate users
    with sqlite3.connect('social_network.db') as sq, driver.session() as session:
        for uid, uname, name in sq.execute("SELECT id, username, name FROM users"):
            session.run(
                """
                MERGE (u:User {id: $id})
                SET u.username = $username, u.name = $name
                """,
                id=uid, username=uname, name=name
            )

    # 2) Migrate posts
    with sqlite3.connect('social_network.db') as sq, driver.session() as session:
        for pid, uid, content, ts in sq.execute("SELECT id, user_id, content, timestamp FROM posts"):
            session.run(
                """
                MATCH (u:User {id: $uid})
                MERGE (p:Post {id: $pid})
                SET p.content = $content, p.timestamp = datetime($ts)
                MERGE (u)-[:POSTED]->(p)
                """,
                uid=uid, pid=pid, content=content, ts=ts
            )

    # 3) Migrate followers
    with sqlite3.connect('social_network.db') as sq, driver.session() as session:
        for follower_id, followee_id in sq.execute("SELECT follower_id, followee_id FROM followers"):
            session.run(
                """
                MATCH (a:User {id: $f}), (b:User {id: $t})
                MERGE (a)-[:FOLLOWS]->(b)
                """,
                f=follower_id, t=followee_id
            )

    driver.close()

if __name__ == "__main__":
    main()
