import yaml


# Load the roles configuration
with open("roles.yaml", 'r') as f:
    ROLES_CONFIG = yaml.safe_load(f)

def apply_authorization_filter(
    pipeline: list, 
    user_context: dict
) -> list:
    """
    Injects authorization filters into a MongoDB pipeline based on user context.
    The 'admin' role bypasses all filters.
    """
    role = user_context.get("role")
    role_config = ROLES_CONFIG['roles'].get(role, {})
    
    # NEW: Special case for admin to bypass all filters
    if role == 'admin':
        return None  # Return the original pipeline with no changes

    auth_filter = None
    
    # Logic for the Developer role
    if role == 'developer':
        allowed_projects = role_config.get('allowed_projects', [])
        if allowed_projects:
            auth_filter = {"$match": {"name": {"$in": allowed_projects}}}

    # If a valid filter was created (e.g., for developer), prepend it
    if auth_filter:
        return [auth_filter]
    else:
        # For any other role, deny access by default
        return None