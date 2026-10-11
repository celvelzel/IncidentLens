from typing import TypedDict

from langgraph.graph import END, START, StateGraph


def test_installed_stategraph_conditional_api():
    class State(TypedDict):
        value: int

    graph = StateGraph(State)
    graph.add_node("increment", lambda state: {"value": state["value"] + 1})
    graph.add_edge(START, "increment")
    graph.add_conditional_edges(
        "increment", lambda state: END if state["value"] == 1 else "increment"
    )
    assert graph.compile().invoke({"value": 0}) == {"value": 1}
