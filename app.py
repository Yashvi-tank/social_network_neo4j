# social_network.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dataclasses import dataclass
from typing import List, Optional

# ======================
# Database Access Layer
# ======================
class Database:
    def __init__(self):
        from dotenv import load_dotenv
        from neo4j import GraphDatabase
        import os

        load_dotenv()
        uri      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user     = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "neo4j")

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._init_constraints()

    def _init_constraints(self):
        with self.driver.session() as session:
            session.run("""
                CREATE CONSTRAINT IF NOT EXISTS
                FOR (u:User) REQUIRE u.id IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT IF NOT EXISTS
                FOR (u:User) REQUIRE u.username IS UNIQUE
            """)

    # User operations
    def create_user(self, username: str, name: str) -> int:
        with self.driver.session() as s:
            row = s.run(
                "MATCH (u:User) RETURN coalesce(max(u.id),0) AS m"
            ).single()
            new_id = row["m"] + 1
            s.run(
                "CREATE (u:User {id:$id,username:$username,name:$name})",
                id=new_id, username=username, name=name
            )
            return new_id

    def get_user(self, user_id: int) -> Optional[dict]:
        with self.driver.session() as s:
            rec = s.run(
                "MATCH (u:User {id:$id}) "
                "RETURN u.id AS id, u.username AS username, u.name AS name",
                id=user_id
            ).single()
            return {'id': rec['id'], 'username': rec['username'], 'name': rec['name']} if rec else None

    def get_all_users(self) -> List[dict]:
        with self.driver.session() as s:
            return [
                {'id': r['id'], 'username': r['username'], 'name': r['name']}
                for r in s.run(
                    "MATCH (u:User) "
                    "RETURN u.id AS id, u.username AS username, u.name AS name "
                    "ORDER BY u.id"
                )
            ]

    # Post operations
    def create_post(self, user_id: int, content: str) -> int:
        with self.driver.session() as s:
            cursor = s.run(
                "MATCH (u:User {id:$uid}) RETURN coalesce(max(p.id),0) AS m",
                uid=user_id
            ).single()
            new_id = cursor["m"] + 1
            s.run(
                "MATCH (u:User {id:$uid}) "
                "CREATE (u)-[:POSTED]->(p:Post {id:$id, content:$content, timestamp: timestamp()})",
                uid=user_id, id=new_id, content=content
            )
            return new_id

    def get_posts_by_user(self, user_id: int) -> List[dict]:
        with self.driver.session() as s:
            return [
                {'id': r['id'], 'content': r['content'], 'timestamp': r['ts'],
                 'username': r['username'], 'name': r['name']}
                for r in s.run(
                    """
                    MATCH (u:User {id:$uid})-[:POSTED]->(p:Post)
                    RETURN p.id AS id, p.content AS content,
                           p.timestamp AS ts,
                           u.username AS username, u.name AS name
                    ORDER BY p.timestamp DESC
                    """,
                    uid=user_id
                )
            ]

    def get_feed(self, user_id: int) -> List[dict]:
        with self.driver.session() as s:
            return [
                {'id': r['id'], 'content': r['content'], 'timestamp': r['ts'],
                 'username': r['username'], 'name': r['name']}
                for r in s.run(
                    """
                    MATCH (u:User {id:$uid})-[:FOLLOWS]->(f:User)-[:POSTED]->(p:Post)
                    RETURN p.id AS id, p.content AS content,
                           p.timestamp AS ts,
                           f.username AS username, f.name AS name
                    ORDER BY p.timestamp DESC
                    """,
                    uid=user_id
                )
            ]

    # Follow operations
    def follow_user(self, follower_id: int, followee_id: int) -> bool:
        with self.driver.session() as s:
            s.run(
                """
                MATCH (a:User {id:$f}), (b:User {id:$t})
                MERGE (a)-[:FOLLOWS]->(b)
                """,
                f=follower_id, t=followee_id
            )
            return True

    def get_followers(self, user_id: int) -> List[dict]:
        with self.driver.session() as s:
            return [
                {'id': r['id'], 'username': r['username'], 'name': r['name']}
                for r in s.run(
                    """
                    MATCH (u:User {id:$uid})<-[:FOLLOWS]-(f:User)
                    RETURN f.id AS id, f.username AS username, f.name AS name
                    """,
                    uid=user_id
                )
            ]

    def get_following(self, user_id: int) -> List[dict]:
        with self.driver.session() as s:
            return [
                {'id': r['id'], 'username': r['username'], 'name': r['name']}
                for r in s.run(
                    """
                    MATCH (u:User {id:$uid})-[:FOLLOWS]->(f:User)
                    RETURN f.id AS id, f.username AS username, f.name AS name
                    """,
                    uid=user_id
                )
            ]

    def unfollow_user(self, follower_id: int, followee_id: int) -> bool:
        with self.driver.session() as s:
            res = s.run(
                """
                MATCH (a:User {id:$f})-[r:FOLLOWS]->(b:User {id:$t})
                DELETE r
                RETURN count(r) AS deleted
                """,
                f=follower_id, t=followee_id
            ).single()
            return res["deleted"] > 0


# ======================
# Web Application (unchanged)
# ======================
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
db = Database()


