from querypilot.agent import parse_action


def test_tool_call_is_parsed():
    assert parse_action("TOOL: get_schema tracks") == ("tool", "get_schema", "tracks")


def test_final_sql_is_parsed():
    kind, _, arg = parse_action("FINAL: SELECT COUNT(*) FROM tracks")
    assert kind == "final"
    assert arg == "SELECT COUNT(*) FROM tracks"


def test_unparseable_reply_terminates_the_loop():
    kind, _, _ = parse_action("I think the answer is 42")
    assert kind == "final"
