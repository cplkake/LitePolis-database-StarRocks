import os
import time
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import text
from contextlib import contextmanager
from litepolis import get_config

DEFAULT_CONFIG = {
    "starrocks_url": os.getenv("STARROCKS_DB_URL", "mysql+pymysql://root:@127.0.0.1:9030/litepolis"),
    "sqlalchemy_engine_pool_size": int(os.getenv("SQLALCHEMY_POOL_SIZE", 10)),
    "sqlalchemy_pool_max_overflow": int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", 20)),
}

database_url = DEFAULT_CONFIG.get("starrocks_url")
engine_pool_size = DEFAULT_CONFIG.get("sqlalchemy_engine_pool_size")
pool_max_overflow = DEFAULT_CONFIG.get("sqlalchemy_pool_max_overflow")

if ("PYTEST_CURRENT_TEST" not in os.environ and
    "PYTEST_VERSION" not in os.environ):
    database_url = get_config("litepolis_database_starrocks", "starrocks_url")
    engine_pool_size = get_config("litepolis_database_starrocks", "sqlalchemy_engine_pool_size")
    pool_max_overflow = get_config("litepolis_database_starrocks", "sqlalchemy_pool_max_overflow")

engine = create_engine(database_url,
                        pool_size=engine_pool_size,
                        max_overflow=pool_max_overflow,
                        pool_timeout=30,
                        pool_pre_ping=True)

@contextmanager
def get_session():
    session = Session(engine, autoflush=False, autocommit=False)
    try:
        yield session
    finally:
        session.close()

def is_starrocks_engine(engine=engine) -> bool:
    """Determine if the engine is connected to StarRocks"""
    # Method 1: Check dialect name
    if 'starrocks' in engine.dialect.name.lower():
        return True
        
    # Method 2: Check connection URL driver
    if 'starrocks' in engine.url.drivername.lower():
        return True
        
    # Method 3: Query database version (fallback)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT CURRENT_VERSION()")).scalar()
            print(version.lower())
            return 'starrocks' in version.lower()
    except:
        return False

def connect_db():
    engine = create_engine(database_url,
                            pool_size=engine_pool_size,
                            max_overflow=pool_max_overflow,
                            pool_timeout=30,
                            pool_pre_ping=True)
    
    if is_starrocks_engine(engine):
        engine.update_execution_options(
            isolation_level="AUTOCOMMIT",  # Bypass transaction issues
            stream_results=False           # Disable streaming for OLAP
        )
    
    return engine

connect_db()

def wait_for_alter_completion(conn, table_name: str, timeout=30):
    """
    Wait for the latest ongoing schema change for a specific table to complete
    using 'ORDER BY CreateTime DESC LIMIT 1'.
    """
    start_time = time.time()
    # Construct the working query using parameter binding for the table name
    # Ensure double quotes are handled correctly if needed by the dialect/driver,
    # SQLAlchemy's parameter binding should typically handle quoting.
    query = text(
        "SHOW ALTER TABLE COLUMN WHERE TableName = :table "
        "ORDER BY CreateTime DESC LIMIT 1"
    )

    print(f"Waiting for latest ALTER job on table '{table_name}' to finish...")

    while time.time() - start_time < timeout:
        # Execute the query to get the latest job for the specific table
        result = conn.execute(query, {"table": table_name}).fetchone() # Fetch one row max

        if not result:
            # No ALTER job found for this table (could be finished long ago or never started)
            print(f"No ALTER job found for table '{table_name}'. Assuming complete.")
            return

        # Check the state of the latest job
        try:
            # --- IMPORTANT: Determine how to access State ---
            # Check the output manually to find the correct column name or index.
            # Example using potential attribute/mapping access:
            current_state = getattr(result, 'State', None)
            if current_state is None and hasattr(result, '_mapping'):
                current_state = result._mapping.get('State')

            if current_state is None:
                 print(f"Warning: Could not determine 'State' column. Row: {result}")
                 # Decide how to handle - perhaps wait and retry? Or raise error?
                 # For now, let's assume it implies waiting is needed.
                 pass # Continue loop to retry query
            elif current_state == 'FINISHED':
                print(f"Latest ALTER job for table '{table_name}' is FINISHED.")
                return # The latest job is finished
            elif current_state in ('CANCELLED', 'FAILED'): # Handle potential failed states
                 raise RuntimeError(f"Latest ALTER job for table '{table_name}' ended with state: {current_state}")

            # If state is PENDING, WAITING_TXN, RUNNING, etc., continue waiting
            # print(f"Waiting for ALTER job on table '{table_name}', current state: {current_state}") # Debugging

        except (AttributeError, KeyError) as e:
            print(f"Error accessing 'State' column: {e}. Row: {result}")
            # Decide how to handle - retry or raise? Let's retry by continuing loop.
            pass

        # Wait before polling again
        time.sleep(1) # Keep poll interval short as we expect state changes

    # If loop finishes without returning, it's a timeout
    raise TimeoutError(f"Latest schema change for {table_name} didn't complete verification in {timeout}s")
