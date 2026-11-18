from jarvis_core import quick

SNAP = {
    "weather": {"ts": 0, "temp_c": 8.44, "humidity": 71, "pressure_hpa": 1009.2, "age_s": 30, "stale": False},
    "dinner": {"state": "calling"},
    "nodes": {"core": {"online": True}, "beacon": {"online": False}, "kitchen": {"online": True}},
}


class Forecast:
    days = [{"desc": "light rain", "high": 9.3, "low": 3.1, "rain": 70},
            {"desc": "partly cloudy", "high": 13.0, "low": 4.0, "rain": 10}]
    sunrise, sunset = "07:21", "16:10"


def ask(text, snap=SNAP, forecast=Forecast(), last=""):
    got = quick.answer(text, snap, forecast, last)
    return got[0] if got else None


def test_time_and_date_without_a_model():
    assert ask("What time is it?").startswith("It's ") and ask("what time is it").count(":") == 1
    assert ask("Hey Jarvis, what's the date today?").startswith("It's ")
    assert " the " in ask("what day is it") and " of " in ask("what day is it")


def test_weather_from_our_own_station_and_forecast():
    assert ask("How cold is it outside?") == "It's 8.4 degrees outside."
    assert ask("what's the weather like") == ("It's 8.4 degrees outside. Today: light rain, a high of 9, "
                                              "70 percent chance of rain.")
    assert ask("Will it rain today?") == "Probably: a 70 percent chance of rain today."
    assert ask("is it going to rain tomorrow") == "Unlikely: only a 10 percent chance of rain tomorrow."
    assert ask("do I need a coat?").startswith("Yes, take a coat")
    assert ask("when's sunset") == "Sunset is at 16:10."


def test_other_places_and_stale_readings_go_to_the_model():
    assert ask("What's the weather like in Paris?") is None
    assert ask("how cold is it in Moscow") is None
    stale = {**SNAP, "weather": {**SNAP["weather"], "stale": True}}
    assert ask("how cold is it outside", snap=stale) is None
    assert ask("will it rain today", forecast=None) is None


def test_house_questions():
    assert ask("Is dinner ready?") == "Yes, dinner is ready."
    assert ask("is everything working") == "Offline: beacon."


def test_sums_are_exact():
    assert ask("What's 23 times 47?") == "23 times 47 is 1,081."
    assert ask("what is 15 percent of 80") == "15 percent of 80 is 12."
    assert ask("2 to the power of 10") == "2 to the power of 10 is 1,024."
    assert ask("what is the square root of 144") == "the square root of 144 is 12."
    assert ask("what's 7 divided by 0") == "You can't divide by zero."
    assert ask("what is 1 000 plus 1") == "1 000 plus 1 is 1,001."


def test_repeat_and_everything_else_goes_to_the_model():
    assert ask("say that again", last="Paris is the capital.") == "Paris is the capital."
    assert ask("say that again") is None
    for q in ("who is the prime minister", "what is 23", "what's the capital of France", "time travel ideas",
              "what is the time in Tokyo", "2 plus apples", "what is 9 to the power of 999999"):
        assert ask(q) is None, q
