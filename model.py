import datetime
import math
from datetime import datetime

import trueskill


class TeamResult:
    def __init__(self, defense: str, offense: str, score: int, switch: bool) -> None:
        self.defense = defense
        self.offense = offense
        self.score = score
        self.switch = switch

    def __str__(self) -> str:
        return f"DEF:{self.defense} OFF:{self.offense} score:{self.score}{' Switched' if self.switch else ''}"


class Game:
    def __init__(self, date: datetime.date, red_team: TeamResult, blue_team: TeamResult):
        self.date = date
        self.red_team = red_team
        self.blue_team = blue_team

    def is_shutout(self) -> bool:
        return self.red_team.score == 0 or self.blue_team.score == 0

    @classmethod
    def of_row(cls, row: list[str]):
        date = datetime.strptime(row[0], '%d/%m/%Y').date()
        red_team = TeamResult(row[1], row[2], try_parse_score(row[5]), row[7] == 'Ja')
        blue_team = TeamResult(row[3], row[4], try_parse_score(row[6]), row[8] == 'Ja')
        return Game(date, red_team, blue_team)

    def __str__(self) -> str:
        return f"{self.date}: Red Team:({self.red_team}) Blue Team:({self.blue_team})"


def format_rating_change(prev_rating: trueskill.Rating, new_rating: trueskill.Rating) -> str:
    return f"Δμ={new_rating.mu - prev_rating.mu:+.2f}, Δσ={new_rating.sigma - prev_rating.sigma:+.2f}, ΔTS={trueskill.expose(new_rating) - trueskill.expose(prev_rating):+.2f}"


class Player:
    def __init__(self, name: str):
        self.name = name
        self._rating = trueskill.Rating()
        self._def_rating = trueskill.Rating()
        self._off_rating = trueskill.Rating()
        self.games = []

    @property
    def rating(self) -> trueskill.Rating:
        return self._rating

    @rating.setter
    def rating(self, value: trueskill.Rating) -> None:
        if not math.isclose(self.rating.mu, value.mu, abs_tol=.01) or not math.isclose(self.rating.sigma, value.sigma, abs_tol=.01):
            print("Updating rating for", self.name, ":", format_rating_change(self.rating, value))
        self._rating = value

    @property
    def def_rating(self) -> trueskill.Rating:
        return self._def_rating

    @def_rating.setter
    def def_rating(self, value: trueskill.Rating) -> None:
        if not math.isclose(self.def_rating.mu, value.mu, abs_tol=.01) or not math.isclose(self.def_rating.sigma, value.sigma, abs_tol=.01):
            print("Updating def_rating for", self.name, ":", format_rating_change(self.def_rating, value))
        self._def_rating = value

    @property
    def off_rating(self) -> trueskill.Rating:
        return self._off_rating

    @off_rating.setter
    def off_rating(self, value: trueskill.Rating) -> None:
        if not math.isclose(self.off_rating.mu, value.mu, abs_tol=.01) or not math.isclose(self.off_rating.sigma, value.sigma, abs_tol=.01):
            print("Updating off_rating for", self.name, ":", format_rating_change(self.off_rating, value))
        self._off_rating = value

    def __str__(self) -> str:
        return f"{self.name}: Rating:(mu={self.rating.mu:.2f}, sigma={self.rating.sigma:.2f}) \
def_rating:(mu={self.def_rating.mu:.2f}, sigma={self.def_rating.sigma:.2f}) \
off_rating:(mu={self.off_rating.mu:.2f}, sigma={self.off_rating.sigma:.2f})"


def try_parse_score(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        return 9
