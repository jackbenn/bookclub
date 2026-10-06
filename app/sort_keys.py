from nameparser import HumanName


def author_sort_key(author: str) -> str:
    """Surname-first sort key, e.g. 'Ursula K. Le Guin' -> 'le guin ursula k.'.

    Handles common suffixes (Jr., III) and name-piece prefixes (Le, Van, De)
    via nameparser. Not perfect — e.g. it assumes Western first/last order,
    so an author given surname-first (as is conventional for some Chinese
    names) will sort on the wrong piece — but good enough for a book list,
    and falls back to the raw string if it can't identify a last name.
    """
    name = HumanName(author)
    if not name.last:
        return author.strip().lower()
    return f"{name.last} {name.first} {name.middle}".strip().lower()


_LEADING_ARTICLES = ("the ", "a ", "an ")


def title_sort_key(title: str) -> str:
    """Library-style title sort key, e.g. 'The Left Hand of Darkness' -> 'left hand of darkness'.

    Drops leading punctuation (quotes, ellipses) and one leading English
    article. A title that is only an article ('A') is kept as is.
    """
    key = title.strip().lower().lstrip("\"'“‘.…¡¿([ ")
    for article in _LEADING_ARTICLES:
        if key.startswith(article) and len(key) > len(article):
            return key[len(article):].lstrip("\"'“‘.…¡¿([ ")
    return key
