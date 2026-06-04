def validate_atom(atom):
    errors = []
    if "content" not in atom:
        errors.append("Missing content")
    if "author_ai" not in atom:
        errors.append("Missing author_ai")
    if errors:
        return False, "; ".join(errors), atom
    return True, None, atom
