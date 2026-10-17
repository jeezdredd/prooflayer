def display_name(user) -> str:
    if user is None:
        return ""
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.username
