from pathlib import Path

def find_package_name():
    """Find the package name by looking for a directory starting with `litepolis_database_`."""
    # Navigate up from tests/ to project root (assuming tests/ is in the project root)
    project_root = Path(__file__).parent.parent.resolve()
    
    # Search for directory matching "litepolis_database_*"
    package_dirs = [
        d for d in project_root.iterdir()
        if d.is_dir() and d.name.startswith("litepolis_database_")
    ]
    
    if not package_dirs:
        raise FileNotFoundError(
            "No package directory found starting with 'litepolis_database_'"
        )
    elif len(package_dirs) > 1:
        raise ValueError(
            f"Found multiple package directories starting with 'litepolis_database_': {[d.name for d in package_dirs]}"
        )
    
    # Validate that it's a Python package (has __init__.py)
    package_dir = package_dirs[0]
    if not (package_dir / "__init__.py").exists():
        raise FileNotFoundError(f"Directory '{package_dir.name}' is not a Python package")
    
    return package_dir.name
