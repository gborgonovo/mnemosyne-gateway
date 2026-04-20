import kuzu
import shutil
import os

if os.path.exists('./test_db'): shutil.rmtree('./test_db')
db = kuzu.Database('./test_db')
conn = kuzu.Connection(db)
conn.execute("CREATE NODE TABLE Node(name STRING, activation double, PRIMARY KEY (name))")
conn.execute("CREATE REL TABLE RELATES(FROM Node TO Node, type STRING)")
conn.execute("MERGE (a:Node {name: 'A'}) ON MATCH SET a.activation = 1.0 ON CREATE SET a.activation = 1.0")
conn.execute("MERGE (b:Node {name: 'B'}) ON MATCH SET b.activation = 0.5 ON CREATE SET b.activation = 0.5")
conn.execute("MATCH (a:Node {name: 'A'}), (b:Node {name: 'B'}) MERGE (a)-[r:RELATES {type: 'LINKED'}]->(b)")
res = conn.execute("MATCH (a)-[r]->(b) RETURN a.name, r.type, b.name")
while res.has_next():
    print(res.get_next())
