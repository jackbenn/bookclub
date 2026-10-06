import pytest

from app.sort_keys import author_sort_key, title_sort_key


@pytest.mark.parametrize("title, key", [
    ("The Dispossessed", "dispossessed"),
    ("A Wizard of Earthsea", "wizard of earthsea"),
    ("An Unkindness of Ghosts", "unkindness of ghosts"),
    ("Middlemarch", "middlemarch"),
    ("Theory of Bastards", "theory of bastards"),   # "The" only as a whole word
    ("Anathem", "anathem"),
    ("Annals of the Former World", "annals of the former world"),
    ("A", "a"),                                       # nothing left to sort on
    ("\"A\" Is for Alibi", "a\" is for alibi"),     # a quoted letter, not an article
    ("'Salem's Lot", "salem's lot"),
    ("...And Ladies of the Club", "and ladies of the club"),
    ("  the remains of the day ", "remains of the day"),
])
def test_title_sort_key(title, key):
    assert title_sort_key(title) == key


def test_title_sort_order():
    titles = ["The Remains of the Day", "Beloved", "A Wizard of Earthsea", "Middlemarch", "The Dispossessed"]
    assert sorted(titles, key=title_sort_key) == [
        "Beloved", "The Dispossessed", "Middlemarch", "The Remains of the Day", "A Wizard of Earthsea",
    ]


@pytest.mark.parametrize("author, key", [
    ("Ursula K. Le Guin", "le guin ursula k."),
    ("Toni Morrison", "morrison toni"),
    ("Martin Luther King Jr.", "king martin luther"),
    ("Homer", "homer"),
])
def test_author_sort_key(author, key):
    assert author_sort_key(author) == key
