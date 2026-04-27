from engine.earthquake_model import run_earthquake
from engine.tsunami_model import run_tsunami
from engine.flood_model import run_flood


def run_disaster(event_type, params, db_conn, financial_model):

    if event_type == "earthquake":
        return run_earthquake(params, db_conn, financial_model)

    elif event_type == "tsunami":
        return run_tsunami(params, db_conn, financial_model)

    elif event_type == "flood":
        return run_flood(params, db_conn, financial_model)

    else:
        return {"error": "Unknown disaster type"}