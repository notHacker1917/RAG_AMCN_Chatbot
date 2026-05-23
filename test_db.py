#!/usr/bin/env python3
"""Quick test of the database configuration."""
import sys
from sqlalchemy import create_engine, text

# Test in-memory database directly
try:
    print("Testing SQLite in-memory database...")
    engine = create_engine("sqlite:///:memory:", echo=False, future=True, connect_args={"check_same_thread": False})
    
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.commit()
        print("✓ Table created successfully")
        
        result = conn.execute(text("SELECT COUNT(*) FROM test"))
        count = result.scalar()
        print(f"✓ Query executed successfully (count={count})")
    
    print("\n✓ In-memory database works!")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
