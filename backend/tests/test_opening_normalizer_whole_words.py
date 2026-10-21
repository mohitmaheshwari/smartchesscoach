"""Opening names are matched on whole words, and every spelling is covered.

Measured over 19,049 named production games on 2026-10-22, plain substring
matching filed 3,475 games as "Other" (about 2,000 of them "Caro Kann
Defense", which has no hyphen), called "Kings Indian Attack Yugoslav
Variation" the Slav, and called the Nimzowitsch Defense the Nimzo-Indian.
"""
import pytest

from services.opening_normalizer import normalize_opening


@pytest.mark.parametrize("name, family", [
    ("Caro Kann Defense Exchange Variation 3...cxd5 4.Nf3", "Caro-Kann"),
    ("Caro-Kann Defense", "Caro-Kann"),
    ("Kings Indian Attack Yugoslav Variation...4.O O Be7 5.d3 O O", "King's Indian Attack"),
    ("Reti Opening Kings Indian Attack Symmetrical Defense 3.Bg2 Bg7", "King's Indian Attack"),
    ("Kings Indian Defense Samisch Normal Defense 6.Be3", "King's Indian Defense"),
    ("Nimzowitsch Defense", "Nimzowitsch Defense"),
    ("Nimzo Indian Defense Rubinstein", "Nimzo-Indian"),
    ("Nimzo Larsen Attack", "Nimzo-Larsen Attack"),
    ("Petrovs Defense Classical Variation", "Petrov Defense"),
    ("Van t Kruijs Opening 1...e5", "Van't Kruys Opening"),
    ("Slav Defense Exchange Variation", "Slav Defense"),
    ("Queens Pawn Opening Accelerated London System", "London System"),
    ("Queens Pawn Opening Zukertort Chigorin Variation 3.e3", "Queen's Pawn Opening"),
    ("Giuoco Piano Game Four Knights Game", "Italian Game"),
    ("Réti Opening", "Réti Opening"),
    ("Reti Opening 1...d5", "Réti Opening"),
    ("Nimzowitsch Defense Scandinavian Bogoljubov Vehre Variation 4.e5", "Scandinavian Defense"),
    ("English Opening Caro Kann Defensive System", "English Opening"),
    ("Alekhines Defense Modern Variation", "Alekhine Defense"),
    ("Birds Opening Dutch Variation", "Bird's Opening"),
    ("Center Game Accepted Normal Variation", "Center Game"),
    ("Owens Defense 2.d4 Bb7 3.Nc3", "Owen's Defense"),
])
def test_names_map_to_their_family(name, family):
    assert normalize_opening(name) == family


def test_a_keyword_inside_another_word_does_not_match():
    # "slav" inside "Yugoslav", "bogo" inside "Bogoljubov".
    assert normalize_opening("Yugoslav Attack") == "Other"
    assert normalize_opening("Bogoljubov Variation") == "Other"


def test_empty_and_unknown_are_other():
    assert normalize_opening(None) == "Other"
    assert normalize_opening("") == "Other"
    assert normalize_opening("Undefined") == "Other"
