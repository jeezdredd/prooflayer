NAME_PART_MAX = 150


def display_name(user) -> str:
    if user is None:
        return ""
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.username


def own_name(user) -> str:
    return f"{user.first_name} {user.last_name}".strip()


def save_name(user, raw) -> None:
    name = " ".join(str(raw or "").split())
    if not name:
        return
    first, _, last = name.partition(" ")
    user.first_name, user.last_name = first[:NAME_PART_MAX], last[:NAME_PART_MAX]
    user.save(update_fields=["first_name", "last_name"])
