"""
Database connection manager for read-only operations.
Example usage and industrial best practices implementation.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv  # pip install python-dotenv
from psycopg_pool import ConnectionPool  # pip install "psycopg[binary]"
from psycopg import OperationalError, InterfaceError

load_dotenv()  # Load .env file variables

# Set up logging for this module
logger = logging.getLogger(__name__)


class DatabaseReader:
    """
    Manages a connection pool to Supabase's PostgreSQL endpoint.
    """

    def __init__(self):
        # DSN loaded from environment variable
        dsn = os.getenv("SUPABASE_DSN") or os.getenv("DATABASE_URL")
        if not dsn:
            raise ValueError("Environment variable SUPABASE_DSN or DATABASE_URL is required")

        # Pool sizing parameters
        min_size = int(os.getenv("DB_POOL_MIN", 1))
        max_size = int(os.getenv("DB_POOL_MAX", 10))

        # Connection timeout parameters
        connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", 30))
        keepalives_idle = int(os.getenv("DB_KEEPALIVES_IDLE", 600))  # 10 minutes
        keepalives_interval = int(os.getenv("DB_KEEPALIVES_INTERVAL", 30))  # 30 seconds
        keepalives_count = int(os.getenv("DB_KEEPALIVES_COUNT", 3))

        # Initialize the connection pool with timeout settings
        self.pool = self._create_connection_pool(dsn, min_size, max_size, 
                                               connect_timeout, keepalives_idle,
                                               keepalives_interval, keepalives_count)

    def _create_connection_pool(self, dsn: str, min_size: int, max_size: int,
                              connect_timeout: int, keepalives_idle: int,
                              keepalives_interval: int, keepalives_count: int) -> ConnectionPool:
        """Create connection pool with proper timeout settings."""
        return ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={
                'connect_timeout': connect_timeout,
                'keepalives_idle': keepalives_idle,
                'keepalives_interval': keepalives_interval,
                'keepalives_count': keepalives_count
            }
        )

    def _reconnect(self):
        """Recreate the connection pool."""
        logger.warning("Recreating connection pool due to connection issues")
        old_pool = self.pool
        
        # Get original connection parameters
        dsn = os.getenv("SUPABASE_DSN") or os.getenv("DATABASE_URL")
        if not dsn:
            raise ValueError("Environment variable SUPABASE_DSN or DATABASE_URL is required")
            
        min_size = int(os.getenv("DB_POOL_MIN", 1))
        max_size = int(os.getenv("DB_POOL_MAX", 10))
        connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", 30))
        keepalives_idle = int(os.getenv("DB_KEEPALIVES_IDLE", 600))
        keepalives_interval = int(os.getenv("DB_KEEPALIVES_INTERVAL", 30))
        keepalives_count = int(os.getenv("DB_KEEPALIVES_COUNT", 3))
        
        try:
            old_pool.close()
        except Exception as e:
            logger.warning(f"Error closing old pool: {e}")
        
        self.pool = self._create_connection_pool(dsn, min_size, max_size,
                                               connect_timeout, keepalives_idle,
                                               keepalives_interval, keepalives_count)
        logger.info("Connection pool recreated successfully")

    def get_stats(self) -> dict:
        """
        Returns a dict of current pool statistics.
        Keys include pool_min, pool_max, pool_size, pool_available, requests_waiting.
        """
        return self.pool.get_stats()

    def execute_query(self, query: str, params: tuple = (), max_retries: int = 3) -> List[tuple]:
        """
        Executes a SQL query and returns all rows with retry logic.
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of tuples containing query results
        """
        return self._execute_with_retry(
            lambda conn, cur: cur.fetchall(),
            query, params, max_retries
        )

    def execute_query_dict(self, query: str, params: tuple = (), max_retries: int = 3) -> List[Dict[str, Any]]:
        """
        Executes a SQL query and returns results as list of dictionaries with retry logic.
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of dictionaries with column names as keys
        """
        def _execute_func(conn, cur):
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            return []
        
        return self._execute_with_retry(_execute_func, query, params, max_retries)
    
    def execute_transaction(self, queries: List[str], params_list: List[tuple] = None, max_retries: int = 3) -> List[Any]:
        """
        Execute multiple queries in a single transaction with retry logic.
        Useful for batch operations that need to be atomic.
        
        Args:
            queries: List of SQL query strings
            params_list: List of parameter tuples for each query (optional)
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of results from each query
        """
        if params_list is None:
            params_list = [() for _ in queries]
        
        if len(queries) != len(params_list):
            raise ValueError("Number of queries must match number of parameter sets")
        
        def _execute_func(conn, cur):
            results = []
            for i, query in enumerate(queries):
                cur.execute(query, params_list[i])
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    results.append([dict(zip(columns, row)) for row in rows])
                else:
                    results.append([])
            return results
        
        return self._execute_with_retry(_execute_func, queries[0], (), max_retries)
    
    def execute_batch_query(self, query: str, params: tuple = (), max_retries: int = 3) -> List[Dict[str, Any]]:
        """
        Execute a multi-statement query (like CREATE TEMP TABLE; SELECT; DROP TABLE) with retry logic.
        Returns only the results from SELECT statements.
        
        Args:
            query: Multi-statement SQL query string
            params: Query parameters tuple
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of dictionaries from the final SELECT statement
        """
        def _execute_func(conn, cur):
            # Split the query into individual statements
            statements = [stmt.strip() for stmt in query.split(';') if stmt.strip()]
            results = []
            
            for statement in statements:
                cur.execute(statement, params if statement == statements[0] else ())
                # Only collect results from SELECT statements
                if cur.description and statement.strip().upper().startswith('SELECT'):
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    results = [dict(zip(columns, row)) for row in rows]
            
            return results
        
        return self._execute_with_retry(_execute_func, query, params, max_retries)

    def execute_query_one(self, query: str, params: tuple = (), max_retries: int = 3) -> Optional[tuple]:
        """
        Executes a SQL query and returns the first row with retry logic.
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            max_retries: Maximum number of retry attempts
            
        Returns:
            First row as tuple or None if no results
        """
        return self._execute_with_retry(
            lambda conn, cur: cur.fetchone(),
            query, params, max_retries
        )

    def execute_query_one_dict(self, query: str, params: tuple = (), max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Executes a SQL query and returns the first row as dictionary with retry logic.
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            max_retries: Maximum number of retry attempts
            
        Returns:
            First row as dictionary or None if no results
        """
        def _execute_func(conn, cur):
            result = cur.fetchone()
            if result and cur.description:
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, result))
            return None
        
        return self._execute_with_retry(_execute_func, query, params, max_retries)

    def _execute_with_retry(self, execute_func, query: str, params: tuple, max_retries: int):
        """
        Execute a database operation with retry logic for connection failures.
        
        Args:
            execute_func: Function to execute after cursor.execute()
            query: SQL query string
            params: Query parameters tuple
            max_retries: Maximum number of retry attempts
            
        Returns:
            Result from execute_func
        """
        for attempt in range(max_retries):
            try:
                with self.pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, params)
                        return execute_func(conn, cur)
                        
            except (OperationalError, InterfaceError) as e:
                error_msg = str(e)
                if ("EOF detected" in error_msg or 
                    "connection" in error_msg.lower() or
                    "closed" in error_msg.lower() or
                    "broken" in error_msg.lower()):
                    
                    logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}: {e}")
                    
                    if attempt < max_retries - 1:
                        # Exponential backoff: 1s, 2s, 4s
                        sleep_time = 2 ** attempt
                        logger.info(f"Retrying in {sleep_time} seconds...")
                        time.sleep(sleep_time)
                        
                        # Recreate connection pool on connection errors
                        try:
                            self._reconnect()
                        except Exception as reconnect_error:
                            logger.error(f"Failed to reconnect: {reconnect_error}")
                            if attempt == max_retries - 1:
                                raise
                        continue
                    else:
                        logger.error(f"Failed after {max_retries} attempts")
                        raise
                else:
                    # Non-connection related errors should not be retried
                    raise
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise
        
        raise Exception(f"Failed to execute query after {max_retries} attempts")

    def test_connection(self) -> bool:
        """
        Test database connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            result = self.execute_query_one("SELECT 1")
            return result is not None
        except Exception:
            return False

    def close(self):
        """
        Gracefully closes all connections in the pool.
        """
        self.pool.close()


# Example usage and helper functions
def create_example_queries():
    """
    Example queries for common database operations.
    This demonstrates how to use the DatabaseReader class.
    """
    db = DatabaseReader()
    
    try:
        # Test connection
        print("Testing connection...")
        if db.test_connection():
            print("✅ Database connection successful")
        else:
            print("❌ Database connection failed")
            return
        
        # Example 1: Get database time
        print("\n1. Getting current database time:")
        result = db.execute_query_one("SELECT NOW() as current_time")
        if result:
            print(f"   Current time: {result[0]}")
        
        # Example 2: Get database version
        print("\n2. Getting database version:")
        result = db.execute_query_one_dict("SELECT version() as db_version")
        if result:
            print(f"   Version: {result['db_version'][:50]}...")
        
        # Example 3: List tables (if you have proper permissions)
        print("\n3. Listing tables in public schema:")
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        tables = db.execute_query_dict(tables_query)
        if tables:
            print(f"   Found {len(tables)} tables:")
            for table in tables[:5]:  # Show first 5 tables
                print(f"   - {table['table_name']}")
            if len(tables) > 5:
                print(f"   ... and {len(tables) - 5} more")
        else:
            print("   No tables found or insufficient permissions")
        
        # Example 4: Pool statistics
        print("\n4. Connection pool statistics:")
        stats = db.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")
    
    except Exception as e:
        print(f"❌ Error during examples: {e}")
    
    finally:
        # Always close the connection pool
        db.close()
        print("\n✅ Database connection pool closed")


if __name__ == "__main__":
    print("🔄 Running DatabaseReader examples...")
    print("=" * 50)
    create_example_queries()
