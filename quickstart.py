import os.path
from enum import Enum
from itertools import chain
from typing import Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from model import *

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = "1cJdsll_263SojLvaTCpqY6A8YRPoUdnG8hvbE6NTMTw"
GAMES_RANGE = "Games!A2:I"
RATINGS_RANGE = "Ratings!A1:K"
OFF_LEADERBOARD_RANGE = "Leaderboards!A1:B"
DEF_LEADERBOARD_RANGE = "Leaderboards!D1:E"


def get_creds():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


# Call the Sheets API
service = build("sheets", "v4", credentials=get_creds())
sheet = service.spreadsheets()


def fetch_rows():
    try:
        result = (
            sheet.values()
            .get(spreadsheetId=SPREADSHEET_ID, range=GAMES_RANGE)
            .execute()
        )
        return result.get("values", [])
    except HttpError as err:
        print(err)


def write_rows(rows, spreadsheet_range):
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=spreadsheet_range,
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()
    print(f"Updated {len(rows)} rows in {spreadsheet_range}")


def build_rows(players):
    rows = [["Player", "Skill_Estimate(µ)", "Confidence(σ)", "99%_TrueSkill",
             "µ_off", "σ_off", "99ts_off", "µ_def", "σ_def", "99ts_def", "Last Updated: " + datetime.now().strftime("%H:%M %d/%m/%Y")]]
    for player in sorted(players.values(), key=lambda p: trueskill.expose(p.rating), reverse=True):
        rows.append(
            [player.name, player.rating.mu, player.rating.sigma, trueskill.expose(player.rating),
             player.off_rating.mu, player.off_rating.sigma, trueskill.expose(player.off_rating),
             player.def_rating.mu, player.def_rating.sigma, trueskill.expose(player.def_rating)])
    print("=====================================")
    for row in rows:
        print(row)
    return rows


def build_offensive_leaderboard(players):
    rows = [["Player", "Offensive Rating"]]
    for player in sorted(players.values(), key=lambda p: trueskill.expose(p.off_rating), reverse=True):
        if trueskill.expose(player.off_rating) < 1:
            break
        rows.append([player.name, trueskill.expose(player.off_rating)])
    print("=====================================")
    for row in rows:
        print(row)
    return rows


def build_defensive_leaderboard(players):
    rows = [["Player", "Defensive Rating"]]
    for player in sorted(players.values(), key=lambda p: trueskill.expose(p.def_rating), reverse=True):
        if trueskill.expose(player.def_rating) < 1:
            break
        rows.append([player.name, trueskill.expose(player.def_rating)])
    print("=====================================")
    for row in rows:
        print(row)
    return rows


class KStrategy(Enum):
    CONSTANT = 0
    BY_SCORE = 1
    SHUTOUT_COUNTS_AS_2_GAMES = 2


def calculate_ratings(games, k_strategy=KStrategy.SHUTOUT_COUNTS_AS_2_GAMES) -> Dict[str, Player]:
    players = build_player_dict(games)
    if k_strategy == KStrategy.SHUTOUT_COUNTS_AS_2_GAMES:
        games = chain.from_iterable([game, game] if game.is_shutout() else [game] for game in games)
    for game in games:
        print("=" * 10, game.date, "=" * 20)
        losing_score, winning_score = sorted([game.red_team.score, game.blue_team.score])
        if k_strategy == KStrategy.BY_SCORE:
            k = 3 if losing_score == 0 else (2 - .1 * (losing_score+1))  # This is a hack to give greater weight to games with a larger score difference
        else:
            k = 1
        kb = 1 if winning_score == game.blue_team.score else k
        kr = 1 if winning_score == game.red_team.score else k
        bd = players[game.blue_team.defense]
        bo = players[game.blue_team.offense]
        rd = players[game.red_team.defense]
        ro = players[game.red_team.offense]
        for player in [bd, bo, rd, ro]:
            player.games.append(game)
        (bd.rating, bo.rating), (rd.rating, ro.rating) = trueskill.rate(
            [[bd.rating, bo.rating],
             [rd.rating, ro.rating]],
            ranks=[game.red_team.score, game.blue_team.score],
            weights=[(1, 1), (k, k)] if game.blue_team.score == winning_score else [(k, k), (1, 1)]
        )

        # Update defense and offense ratings
        # When players switch, model it as a team of 4 players playing at half capacity.
        ((bd.def_rating, bd.off_rating, bo.def_rating, bo.off_rating),
         (rd.def_rating, rd.off_rating, ro.def_rating, ro.off_rating)) = trueskill.rate(
            [[bd.def_rating, bd.off_rating, bo.def_rating, bo.off_rating],
             [rd.def_rating, rd.off_rating, ro.def_rating, ro.off_rating]],
            ranks=[game.red_team.score, game.blue_team.score],
            weights=[(.5*kb, .5*kb, .5*kb, .5*kb) if game.blue_team.switch else (kb, 0, 0, kb),
                     (.5*kr, .5*kr, .5*kr, .5*kr) if game.red_team.switch else (kr, 0, 0, kr)])

        print("Red Team:", game.red_team.score, "Switched" if game.red_team.switch else "")
        print(f"\tDEF:", rd)
        print("\tOFF:", ro)
        print("Blue Team:", game.blue_team.score, "Switched" if game.blue_team.switch else "")
        print("\tDEF:", bd)
        print("\tOFF:", bo)
    return players


def build_player_dict(games):
    player_names = set(chain.from_iterable([[game.blue_team.defense, game.blue_team.offense,
                                             game.red_team.defense, game.red_team.offense]
                                            for game in games]))
    return {name: Player(name) for name in player_names}


def predict_result(game: Game, players: Dict[str, Player]):
    bd = players[game.blue_team.defense]
    bo = players[game.blue_team.offense]
    rd = players[game.red_team.defense]
    ro = players[game.red_team.offense]
    red_team_rating = trueskill.expose(rd.rating) + trueskill.expose(ro.rating)
    blue_team_rating = trueskill.expose(bd.rating) + trueskill.expose(bo.rating)
    if red_team_rating > blue_team_rating:
        return game.red_team
    else:
        return game.blue_team


def main():
    trueskill.setup(draw_probability=0)
    games = [Game.of_row(row) for row in fetch_rows()]

    players = calculate_ratings(games)
    rows = build_rows(players)
    off_leaderboard = build_offensive_leaderboard(players)
    def_leaderboard = build_defensive_leaderboard(players)

    write_rows(rows, RATINGS_RANGE)
    write_rows(off_leaderboard, OFF_LEADERBOARD_RANGE)
    write_rows(def_leaderboard, DEF_LEADERBOARD_RANGE)


if __name__ == "__main__":
    main()
