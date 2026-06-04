import kuzu
import os

DB_PATH = os.path.expanduser(
    "~/Documents/NEVA/tools/mcp_executor/graph/kuzu_db"
)

os.makedirs(DB_PATH, exist_ok=True)

db = kuzu.Database(DB_PATH)
conn = kuzu.Connection(db)


def init_schema():
    conn.execute("""
        CREATE NODE TABLE IF NOT EXISTS Execution(
            id STRING,
            timestamp DOUBLE,
            action STRING,
            PRIMARY KEY(id)
        )
    """)

    conn.execute("""
        CREATE REL TABLE IF NOT EXISTS CALLS(
            FROM Execution TO Execution,
            type STRING
        )
    """)


def insert_atoms(atoms: list):
    for a in atoms:
        conn.execute(
            """
            CREATE (:Execution {
                id: $id,
                timestamp: $timestamp,
                action: $action
            })
            """,
            {
                "id": a["id"],
                "timestamp": a["timestamp"],
                "action": a["action"]
            }
        )

        conn.execute(
            """
            MATCH (a:Execution {id: $id})
            MATCH (b:Execution {id: 'NEVA_ROOT'})
            CREATE (b)-[:CALLS {type: 'EXECUTION'}]->(a)
            """,
            {"id": a["id"]}
        )


def ensure_root():
    conn.execute("""
        CREATE (:Execution {
            id: 'NEVA_ROOT',
            timestamp: 0,
            action: 'root'
        })
    """)
