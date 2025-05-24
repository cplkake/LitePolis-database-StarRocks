# Combined file: registry, generator, and orchestration logic

import sqlalchemy
from sqlalchemy.schema import Column, PrimaryKeyConstraint, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy import Integer, Boolean, text
from sqlmodel import SQLModel, Field, create_engine # Assuming create_engine is used elsewhere or passed in
import datetime
from typing import Optional, Dict, Any, Type, Tuple
import functools
import os
import sys
import importlib
import pkgutil
from pathlib import Path
import traceback # For better error printing
import time # Import the time module

from .utils import engine, is_starrocks_engine, wait_for_alter_completion

# ==============================================================================
# 1. Decorator and Registry Logic
# ==============================================================================

# Central registry to store model classes and their special DDL hints
# Structure: { 'table_name': {'model_class': ModelType, 'hints': {...}} }
_MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {}

def register_table(
    distributed_by: Optional[str] = None,
    properties: Optional[Dict[str, str]] = None
):
    """
    Decorator to register a SQLModel class and its special DDL hints
    for custom DDL generation.
    """
    def decorator(cls: Type[SQLModel]):
        if not issubclass(cls, SQLModel):
            raise TypeError(f"{cls.__name__} must be a SQLModel subclass.")

        # Store hints directly on the class temporarily.
        # The registry will be populated later using metadata.
        hints = {
            'distributed_by': distributed_by,
            'properties': properties or {}, # Ensure properties is a dict
        }
        setattr(cls, '_specialdb_hints', hints)
        setattr(cls, '_is_registered_project_model', True) # Mark for discovery

        # functools.wraps is not needed here as we return the original class 'cls'
        return cls # Return the original decorated class
    return decorator

def get_hints_for_table(table_name: str) -> Optional[Dict[str, Any]]:
    """Retrieves hints from the registry based on table name."""
    # Ensure populate_registry was called first
    return _MODEL_REGISTRY.get(table_name, {}).get('hints')

def populate_registry(metadata: sqlalchemy.MetaData):
    """
    Populates the _MODEL_REGISTRY using table names from metadata
    after all decorated models are imported and defined.
    """
    global _MODEL_REGISTRY
    _MODEL_REGISTRY = {} # Clear previous state
    print(f"Populating registry from metadata with {len(metadata.tables)} tables...")

    # Build a temporary map of known subclasses to check against
    known_models = {}
    queue = SQLModel.__subclasses__() # Start from SQLModel base
    processed = set()
    while queue:
        cls = queue.pop(0)
        if cls not in processed:
            processed.add(cls)
            # Only consider classes marked by our decorator
            if getattr(cls, '_is_registered_project_model', False):
                # Associate by class name for now, will link via table later
                known_models[cls.__name__] = cls
            queue.extend(cls.__subclasses__())

    if not known_models:
         print("Warning: No models marked with '@register_table' found during registry population.")
         # This might happen if imports failed or decorators weren't used.

    # Iterate through tables found by SQLAlchemy
    for table_name, table_obj in metadata.tables.items():
        found_model = None
        # Find the model class that corresponds to this table object
        # This relies on the __table__ attribute being correctly set by SQLModel
        for model_cls in known_models.values():
             if hasattr(model_cls, '__table__') and model_cls.__table__ is table_obj:
                  found_model = model_cls
                  break

        if found_model:
            hints = getattr(found_model, '_specialdb_hints', {})
            _MODEL_REGISTRY[table_name] = {'model_class': found_model, 'hints': hints}
            # print(f"  Registered: {table_name} -> {found_model.__name__}") # Debug print
        # else:
        #     print(f"  Debug: No registered model class found for table object {table_name}") # Debug print


# ==============================================================================
# 2. Custom DDL Generation Logic
# ==============================================================================

# NOTE: Removed @classmethod as this is now a standalone helper
def _format_col_ddl_standalone(column: Column, dialect, is_autoinc: bool) -> Optional[str]:
    """
    Helper to format a single column's DDL definition.
    Ensures FK integer columns match PK integer columns (as BIGINT).
    Uses the provided dialect for type/default compilation.
    """
    if not isinstance(column, Column): return None
    col_name = column.name; col_type_str = ""; is_pk_col = column.primary_key

    try:
        import enum
        target_type_str = None
        if is_pk_col and isinstance(column.type, Integer):
             target_type_str = "BIGINT"
        elif isinstance(column.type, Integer) and column.foreign_keys:
             fk = next(iter(column.foreign_keys), None)
             if fk and fk.column is not None:
                 if fk.column.primary_key and isinstance(fk.column.type, Integer):
                      target_type_str = "BIGINT"
        elif repr(column.type) == "AutoString()" and not getattr(column.type, 'length', None):
            # Option B.1: Use StarRocks native STRING type if valid
            target_type_str = "STRING"
            # Option B.2: Use a default VARCHAR length if STRING isn't preferred/valid
            # default_varchar_len = 255
            # target_type_str = f"VARCHAR({default_varchar_len})"
            print(f"Warning: Column '{col_name}' is 'str' without max_length. Generating '{target_type_str}' type.")
        elif isinstance(column.type, sqlalchemy.Enum):
            enum_values_to_check = column.type.enums

            if enum_values_to_check:
                 max_len = max(len(str(v)) for v in enum_values_to_check)
                 # Add a small buffer maybe? Or just use exact max.
                 target_type_str = f"VARCHAR({max_len})"
                 print(f"    Decision: ENUM type -> {target_type_str}")
            else:
                 # Enum defined but no values found? Fallback needed.
                 print(f"    Warning: Enum type found for {col_name} but no values detected. Falling back.")
                 # Fallback to default compilation might generate ENUM(), causing error.
                 # Maybe default to VARCHAR(255)?
                 target_type_str = "VARCHAR(255)" # Safer fallback
                 print(f"    Decision: ENUM type (no values) -> {target_type_str}")
        if target_type_str: col_type_str = target_type_str
        else: col_type_str = column.type.compile(dialect=dialect) # Use passed dialect
    except Exception as e: print(f"W: Compiling type {col_name}: {e}"); col_type_str = repr(column.type)
    if '()' in col_type_str: col_type_str = col_type_str.replace('()', '')

    constraints = []
    if not column.nullable: constraints.append("NOT NULL")
    if is_autoinc: constraints.append("AUTO_INCREMENT")
    if column.server_default is not None:
        if not isinstance(column.type, Boolean):
             default_compiler = dialect.default_compiler(dialect)
             try:
                 # Pass dialect here too for consistent default formatting
                 default_str = default_compiler.process(column.server_default, dialect=dialect)
                 if default_str and default_str.upper() != 'NULL': constraints.append(f"DEFAULT {default_str}")
             except Exception as e: print(f"W: Compiling default {col_name}: {e}")
    constraints_str = " ".join(constraints)

    comment_str = ""
    if column.comment: escaped_comment = column.comment.replace("'", "''"); comment_str = f"COMMENT '{escaped_comment}'"

    parts = [f"`{col_name}`", col_type_str, constraints_str, comment_str]
    return " ".join(p for p in parts if p)


# NOTE: dialect argument is now mandatory (no default)
def generate_custom_ddl_for_table(table: sqlalchemy.Table, hints: Dict[str, Any], dialect: sqlalchemy.engine.interfaces.Dialect):
    """
    Generates the specific DDL for one table using hints and the provided dialect.
    Handles column order and key placement.
    """
    table_name = table.name
    ddl_parts = []
    key_clause = None; key_col_names_ordered = []; key_constraint = None; is_autoinc_pk = False

    # --- Determine KEY clause and Ordered Key Columns ---
    if table.primary_key:
        key_constraint = table.primary_key
        key_col_names_ordered = [c.name for c in key_constraint.columns]
        pk_cols_quoted = [f"`{name}`" for name in key_col_names_ordered]
        key_clause = f"PRIMARY KEY({', '.join(pk_cols_quoted)})"
        is_autoinc_pk = any(isinstance(c.type, Integer) and (c.autoincrement is True or c.autoincrement == 'auto') for c in key_constraint.columns)
    else:
        unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        if unique_constraints:
            key_constraint = unique_constraints[0]
            key_col_names_ordered = [c.name for c in key_constraint.columns]
            uk_cols_quoted = [f"`{name}`" for name in key_col_names_ordered]
            key_clause = f"UNIQUE KEY({', '.join(uk_cols_quoted)})"

    if not key_clause: raise ValueError(f"Table '{table_name}' must have PK or UK defined.")

    # --- Order Columns for Definition ---
    key_columns_ordered_objs = [table.columns[name] for name in key_col_names_ordered]
    non_key_columns = [col for col in table.columns if col.name not in key_col_names_ordered]
    columns_in_ddl_order = key_columns_ordered_objs + non_key_columns

    # --- Format Column Definitions ---
    column_ddl_lines = []
    for column in columns_in_ddl_order:
        should_autoinc_this_col = (column.primary_key and is_autoinc_pk and isinstance(column.type, Integer))
        # Pass the mandatory dialect to the helper
        col_def = _format_col_ddl_standalone(column, dialect, is_autoinc=should_autoinc_this_col)
        if col_def: column_ddl_lines.append(f"    {col_def}") # Indent columns

    # --- Assemble CREATE TABLE block ---
    ddl_parts.append(f"CREATE TABLE IF NOT EXISTS `{table_name}` (")
    if column_ddl_lines: ddl_parts.append(",\n".join(column_ddl_lines))

    ddl_parts.append(")")

    # --- Append KEY clause ---
    ddl_parts.append(key_clause)

    # --- Format Foreign Keys for PROPERTIES ---
    fk_defs = []
    for constraint in table.foreign_key_constraints:
         if isinstance(constraint, ForeignKeyConstraint):
            local_cols=[f"{c}" for c in constraint.columns.keys()]; ref_cols=[]; ref_table=None
            for el in constraint.elements: ref_table = el.column.table.name; ref_cols.append(f"{el.column.name}")
            if local_cols and ref_table and ref_cols and ref_table != table_name: fk_defs.append(f"({','.join(local_cols)}) REFERENCES {ref_table}({','.join(ref_cols)})")
    fk_string = ";".join(fk_defs)

    # --- Prepare PROPERTIES clause (using hints) ---
    properties_dict = hints.get('properties', {}).copy()
    if fk_string: properties_dict["foreign_key_constraints"] = fk_string
    prop_items = [f'"{k}" = "{v}"' for k, v in properties_dict.items()]
    properties_clause = ""
    if prop_items:
        prop_lines = ',\n        '.join(prop_items) # Indent properties
        properties_clause = f"PROPERTIES (\n        {prop_lines}\n    )" # Add indentation

    # --- Prepare DISTRIBUTED BY clause (using hints) ---
    distributed_by_clause = ""
    distributed_by_val = hints.get('distributed_by')
    if distributed_by_val: distributed_by_clause = f"DISTRIBUTED BY {distributed_by_val}"

    # --- Combine all parts ---
    final_ddl_string = "\n".join(ddl_parts)
    if distributed_by_clause: final_ddl_string += f"\n{distributed_by_clause}"
    if properties_clause: final_ddl_string += f"\n{properties_clause}"
    final_ddl_string += ";"
    return final_ddl_string


# ==============================================================================
# 3. Orchestration Logic (Example)
# ==============================================================================

# Assume these are defined elsewhere and imported if needed
# from .utils import engine, is_starrocks_engine, wait_for_alter_completion

def create_db_and_tables():
    """
    Creates all tables, using standard or custom DDL based on dialect.
    Relies on models being imported beforehand.
    """
    metadata = SQLModel.metadata

    # --- Populate registry using Metadata AFTER models are imported ---
    try:
        populate_registry(metadata) # Must be called after models are defined/imported
        print(f"Model registry populated with {len(_MODEL_REGISTRY)} entries.")
    except Exception as e:
        print(f"Error during registry population: {e}")
        traceback.print_exc()
        return # Cannot proceed without registry if special DB

    target_dialect = engine.dialect # Get the actual dialect

    if is_starrocks_engine(): # Use your specific check here
        print(f"StarRocks Database detected ({target_dialect.name}). Generating custom DDL...")
        try:
            sorted_tables = metadata.sorted_tables
            print(f"Processing {len(sorted_tables)} tables in dependency order.")
            ddl_statements = []
            generation_errors = False
            for table in sorted_tables:
                registry_entry = _MODEL_REGISTRY.get(table.name)
                hints = registry_entry.get('hints') if registry_entry else None

                if hints is None: # Use registry_entry presence check
                     # Check if it's a table defined without the decorator
                     if table.name in metadata.tables:
                         print(f"Note: Table '{table.name}' found in metadata but not registered "
                               f"via @register_table. Assuming standard DDL needed (or skip).")
                         # Decide: Skip? Or try standard DDL? Forcing custom path now.
                         # If you have mixed models, add logic here.
                         # For now, we only generate DDL for registered tables.
                         print(f"Warning: No hints found for {table.name}. Skipping custom DDL generation.")
                     continue # Skip if not registered for custom DDL

                print(f"Generating custom DDL for: {table.name}")
                try:
                    # ---> Pass the CORRECT DIALECT <---
                    ddl = generate_custom_ddl_for_table(table, hints, dialect=target_dialect)
                    ddl_statements.append(ddl)
                except Exception as e:
                    print(f"  ERROR generating DDL for {table.name}: {e}")
                    generation_errors = True

            if generation_errors:
                 print("\nErrors occurred during DDL generation. Aborting execution.")
                 return

            if ddl_statements:
                print("\nExecuting custom DDL statements...")
                try:
                    with engine.connect() as connection:
                        for i, stmt in enumerate(ddl_statements):
                            print(f"Executing statement {i+1}/{len(ddl_statements)} for table {sorted_tables[i].name}...")
                            # print(f"SQL:\n{stmt}\n") # Uncomment to print SQL before execution
                            connection.execute(sqlalchemy.text(stmt))
                            # Call wait function
                            wait_for_alter_completion(connection, sorted_tables[i].name)
                            # Add explicit sleep to allow metadata propagation
                            print(f"  Sleeping for 2 seconds after creating {sorted_tables[i].name}...")
                            time.sleep(2)
                        # Only commit once after all statements if not using autocommit
                        if not connection.dialect.supports_statement_cache: # Heuristic for needing commit
                            connection.commit()
                    print("Custom DDL execution completed.")
                except Exception as e:
                    print(f"\n!!! DATABASE ERROR DURING CUSTOM DDL EXECUTION !!!")
                    print(f"Error: {e}")
                    # Consider printing the failed statement if error is hard to trace
                    # print(f"Failed statement was likely #{i+1}:\n{stmt}")
                    traceback.print_exc()


        except Exception as e:
            print(f"An error occurred during custom DDL generation/execution phase: {e}")
            traceback.print_exc()

    else:
        print(f"Standard Database ({target_dialect.name}) detected. Using metadata.create_all()...")
        try:
            # Ensure all models are loaded/imported before this!
            metadata.create_all(engine)
            print("Standard schema creation completed.")
        except Exception as e:
            print(f"DATABASE ERROR during metadata.create_all(): {e}")
            traceback.print_exc()


# ==============================================================================
# 4. Example Usage Block (for testing this file directly)
# ==============================================================================
if __name__ == '__main__':

    print("Defining example models...")
    # --- Example Model Definitions ---
    # Place these in separate files (e.g., models/user.py) in a real project
    # Make sure they are imported before create_db_and_tables() is called.

    @register_table(
        distributed_by="HASH(id)",
        properties={
            "enable_persistent_index": "true",
            "compression": "LZ4",
            "bloom_filter_columns": "email"
        }
    )
    class User(SQLModel, table=True):
        __tablename__ = "users"
        id: Optional[int] = Field(default=None, primary_key=True)
        email: str = Field(unique=True, sa_column_kwargs={"comment": "Unique email address"})
        auth_token: str = Field(max_length=2048, sa_column_kwargs={"comment": "Auth token"})
        is_admin: bool = Field(default=False, sa_column_kwargs={"comment": "Admin status"})

    @register_table(
        distributed_by="HASH(id)",
        properties={"compression": "LZ4"}
    )
    class Conversation(SQLModel, table=True):
        __tablename__ = "conversations"
        id: Optional[int] = Field(default=None, primary_key=True)
        user_id: Optional[int] = Field(default=None, foreign_key="users.id", sa_column_kwargs={"comment": "Creator ID"})
        title: str = Field(nullable=False, sa_column_kwargs={"comment": "Conv Title"})

    print("Example models defined.")

    # --- Run the creation logic ---
    create_db_and_tables()