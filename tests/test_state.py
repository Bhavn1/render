from __future__ import annotations

import asyncio
import datetime
import functools
import os
from typing import Dict, List
from unittest.mock import AsyncMock, Mock

import pytest
from plotly.graph_objects import Figure

import reflex as rx
from reflex.base import Base
from reflex.constants import APP_VAR, IS_HYDRATED, RouteVar, SocketEvent
from reflex.event import Event, EventHandler
from reflex.state import (
    ImmutableStateError,
    LockExpiredError,
    State,
    StateManager,
    StateProxy,
    StateUpdate,
)
from reflex.utils import format, prerequisites
from reflex.vars import BaseVar, ComputedVar, ReflexDict, ReflexList, ReflexSet

from .states import GenState

CI = bool(os.environ.get("CI", False))
LOCK_EXPIRATION = 2000 if CI else 100
LOCK_EXPIRE_SLEEP = 2.5 if CI else 0.2


class Object(Base):
    """A test object fixture."""

    prop1: int = 42
    prop2: str = "hello"


class TestState(State):
    """A test state."""

    # Set this class as not test one
    __test__ = False

    num1: int
    num2: float = 3.14
    key: str
    map_key: str = "a"
    array: List[float] = [1, 2, 3.14]
    mapping: Dict[str, List[int]] = {"a": [1, 2, 3], "b": [4, 5, 6]}
    obj: Object = Object()
    complex: Dict[int, Object] = {1: Object(), 2: Object()}
    fig: Figure = Figure()
    dt: datetime.datetime = datetime.datetime.fromisoformat("1989-11-09T18:53:00+01:00")

    @ComputedVar
    def sum(self) -> float:
        """Dynamically sum the numbers.

        Returns:
            The sum of the numbers.
        """
        return self.num1 + self.num2

    @ComputedVar
    def upper(self) -> str:
        """Uppercase the key.

        Returns:
            The uppercased key.
        """
        return self.key.upper()

    def do_something(self):
        """Do something."""
        pass


class ChildState(TestState):
    """A child state fixture."""

    value: str
    count: int = 23

    def change_both(self, value: str, count: int):
        """Change both the value and count.

        Args:
            value: The new value.
            count: The new count.
        """
        self.value = value.upper()
        self.count = count * 2


class ChildState2(TestState):
    """A child state fixture."""

    value: str


class GrandchildState(ChildState):
    """A grandchild state fixture."""

    value2: str

    def do_nothing(self):
        """Do something."""
        pass


@pytest.fixture
def test_state() -> TestState:
    """A state.

    Returns:
        A test state.
    """
    return TestState()  # type: ignore


@pytest.fixture
def child_state(test_state) -> ChildState:
    """A child state.

    Args:
        test_state: A test state.

    Returns:
        A test child state.
    """
    child_state = test_state.get_substate(["child_state"])
    assert child_state is not None
    return child_state


@pytest.fixture
def child_state2(test_state) -> ChildState2:
    """A second child state.

    Args:
        test_state: A test state.

    Returns:
        A second test child state.
    """
    child_state2 = test_state.get_substate(["child_state2"])
    assert child_state2 is not None
    return child_state2


@pytest.fixture
def grandchild_state(child_state) -> GrandchildState:
    """A state.

    Args:
        child_state: A child state.

    Returns:
        A test state.
    """
    grandchild_state = child_state.get_substate(["grandchild_state"])
    assert grandchild_state is not None
    return grandchild_state


def test_base_class_vars(test_state):
    """Test that the class vars are set correctly.

    Args:
        test_state: A state.
    """
    fields = test_state.get_fields()
    cls = type(test_state)

    for field in fields:
        if field in test_state.get_skip_vars():
            continue
        prop = getattr(cls, field)
        assert isinstance(prop, BaseVar)
        assert prop.name == field

    assert cls.num1.type_ == int
    assert cls.num2.type_ == float
    assert cls.key.type_ == str


def test_computed_class_var(test_state):
    """Test that the class computed vars are set correctly.

    Args:
        test_state: A state.
    """
    cls = type(test_state)
    vars = [(prop.name, prop.type_) for prop in cls.computed_vars.values()]
    assert ("sum", float) in vars
    assert ("upper", str) in vars


def test_class_vars(test_state):
    """Test that the class vars are set correctly.

    Args:
        test_state: A state.
    """
    cls = type(test_state)
    assert set(cls.vars.keys()) == {
        IS_HYDRATED,  # added by hydrate_middleware to all State
        "num1",
        "num2",
        "key",
        "map_key",
        "array",
        "mapping",
        "obj",
        "complex",
        "sum",
        "upper",
        "fig",
        "dt",
    }


def test_event_handlers(test_state):
    """Test that event handler is set correctly.

    Args:
        test_state: A state.
    """
    expected = {
        "do_something",
        "set_array",
        "set_complex",
        "set_fig",
        "set_key",
        "set_mapping",
        "set_num1",
        "set_num2",
        "set_obj",
    }

    cls = type(test_state)
    assert set(cls.event_handlers.keys()).intersection(expected) == expected


def test_default_value(test_state):
    """Test that the default value of a var is correct.

    Args:
        test_state: A state.
    """
    assert test_state.num1 == 0
    assert test_state.num2 == 3.14
    assert test_state.key == ""
    assert test_state.sum == 3.14
    assert test_state.upper == ""


def test_computed_vars(test_state):
    """Test that the computed var is computed correctly.

    Args:
        test_state: A state.
    """
    test_state.num1 = 1
    test_state.num2 = 4
    assert test_state.sum == 5
    test_state.key = "hello world"
    assert test_state.upper == "HELLO WORLD"


def test_dict(test_state):
    """Test that the dict representation of a state is correct.

    Args:
        test_state: A state.
    """
    substates = {"child_state", "child_state2"}
    assert set(test_state.dict().keys()) == set(test_state.vars.keys()) | substates
    assert (
        set(test_state.dict(include_computed=False).keys())
        == set(test_state.base_vars) | substates
    )


def test_format_state(test_state):
    """Test that the format state is correct.

    Args:
        test_state: A state.
    """
    formatted_state = format.format_state(test_state.dict())
    exp_formatted_state = {
        "array": [1, 2, 3.14],
        "child_state": {"count": 23, "grandchild_state": {"value2": ""}, "value": ""},
        "child_state2": {"value": ""},
        "complex": {
            1: {"prop1": 42, "prop2": "hello"},
            2: {"prop1": 42, "prop2": "hello"},
        },
        "dt": "1989-11-09 18:53:00+01:00",
        "fig": [],
        "is_hydrated": False,
        "key": "",
        "map_key": "a",
        "mapping": {"a": [1, 2, 3], "b": [4, 5, 6]},
        "num1": 0,
        "num2": 3.14,
        "obj": {"prop1": 42, "prop2": "hello"},
        "sum": 3.14,
        "upper": "",
    }
    assert formatted_state == exp_formatted_state


def test_format_state_datetime():
    """Test that the format state is correct for datetime classes."""

    class DateTimeState(State):
        d: datetime.date = datetime.date.fromisoformat("1989-11-09")
        dt: datetime.datetime = datetime.datetime.fromisoformat(
            "1989-11-09T18:53:00+01:00"
        )
        t: datetime.time = datetime.time.fromisoformat("18:53:00+01:00")
        td: datetime.timedelta = datetime.timedelta(days=11, minutes=11)

    formatted_state = format.format_state(DateTimeState().dict())
    exp_formatted_state = {
        "d": "1989-11-09",
        "dt": "1989-11-09 18:53:00+01:00",
        "is_hydrated": False,
        "t": "18:53:00+01:00",
        "td": "11 days, 0:11:00",
    }
    assert formatted_state == exp_formatted_state


def test_default_setters(test_state):
    """Test that we can set default values.

    Args:
        test_state: A state.
    """
    for prop_name in test_state.base_vars:
        # Each base var should have a default setter.
        assert hasattr(test_state, f"set_{prop_name}")


def test_class_indexing_with_vars():
    """Test that we can index into a state var with another var."""
    prop = TestState.array[TestState.num1]
    assert str(prop) == "{test_state.array.at(test_state.num1)}"

    prop = TestState.mapping["a"][TestState.num1]
    assert str(prop) == '{test_state.mapping["a"].at(test_state.num1)}'

    prop = TestState.mapping[TestState.map_key]
    assert str(prop) == "{test_state.mapping[test_state.map_key]}"


def test_class_attributes():
    """Test that we can get class attributes."""
    prop = TestState.obj.prop1
    assert str(prop) == "{test_state.obj.prop1}"

    prop = TestState.complex[1].prop1
    assert str(prop) == "{test_state.complex[1].prop1}"


def test_get_parent_state():
    """Test getting the parent state."""
    assert TestState.get_parent_state() is None
    assert ChildState.get_parent_state() == TestState
    assert ChildState2.get_parent_state() == TestState
    assert GrandchildState.get_parent_state() == ChildState


def test_get_substates():
    """Test getting the substates."""
    assert TestState.get_substates() == {ChildState, ChildState2}
    assert ChildState.get_substates() == {GrandchildState}
    assert ChildState2.get_substates() == set()
    assert GrandchildState.get_substates() == set()


def test_get_name():
    """Test getting the name of a state."""
    assert TestState.get_name() == "test_state"
    assert ChildState.get_name() == "child_state"
    assert ChildState2.get_name() == "child_state2"
    assert GrandchildState.get_name() == "grandchild_state"


def test_get_full_name():
    """Test getting the full name."""
    assert TestState.get_full_name() == "test_state"
    assert ChildState.get_full_name() == "test_state.child_state"
    assert ChildState2.get_full_name() == "test_state.child_state2"
    assert GrandchildState.get_full_name() == "test_state.child_state.grandchild_state"


def test_get_class_substate():
    """Test getting the substate of a class."""
    assert TestState.get_class_substate(("child_state",)) == ChildState
    assert TestState.get_class_substate(("child_state2",)) == ChildState2
    assert ChildState.get_class_substate(("grandchild_state",)) == GrandchildState
    assert (
        TestState.get_class_substate(("child_state", "grandchild_state"))
        == GrandchildState
    )
    with pytest.raises(ValueError):
        TestState.get_class_substate(("invalid_child",))
    with pytest.raises(ValueError):
        TestState.get_class_substate(
            (
                "child_state",
                "invalid_child",
            )
        )


def test_get_class_var():
    """Test getting the var of a class."""
    assert TestState.get_class_var(("num1",)).equals(TestState.num1)
    assert TestState.get_class_var(("num2",)).equals(TestState.num2)
    assert ChildState.get_class_var(("value",)).equals(ChildState.value)
    assert GrandchildState.get_class_var(("value2",)).equals(GrandchildState.value2)
    assert TestState.get_class_var(("child_state", "value")).equals(ChildState.value)
    assert TestState.get_class_var(
        ("child_state", "grandchild_state", "value2")
    ).equals(
        GrandchildState.value2,
    )
    assert ChildState.get_class_var(("grandchild_state", "value2")).equals(
        GrandchildState.value2,
    )
    with pytest.raises(ValueError):
        TestState.get_class_var(("invalid_var",))
    with pytest.raises(ValueError):
        TestState.get_class_var(
            (
                "child_state",
                "invalid_var",
            )
        )


def test_set_class_var():
    """Test setting the var of a class."""
    with pytest.raises(AttributeError):
        TestState.num3  # type: ignore
    TestState._set_var(BaseVar(name="num3", type_=int).set_state(TestState))
    var = TestState.num3  # type: ignore
    assert var.name == "num3"
    assert var.type_ == int
    assert var.state == TestState.get_full_name()


def test_set_parent_and_substates(test_state, child_state, grandchild_state):
    """Test setting the parent and substates.

    Args:
        test_state: A state.
        child_state: A child state.
        grandchild_state: A grandchild state.
    """
    assert len(test_state.substates) == 2
    assert set(test_state.substates) == {"child_state", "child_state2"}

    assert child_state.parent_state == test_state
    assert len(child_state.substates) == 1
    assert set(child_state.substates) == {"grandchild_state"}

    assert grandchild_state.parent_state == child_state
    assert len(grandchild_state.substates) == 0


def test_get_child_attribute(test_state, child_state, child_state2, grandchild_state):
    """Test getting the attribute of a state.

    Args:
        test_state: A state.
        child_state: A child state.
        child_state2: A child state.
        grandchild_state: A grandchild state.
    """
    assert test_state.num1 == 0
    assert child_state.value == ""
    assert child_state2.value == ""
    assert child_state.count == 23
    assert grandchild_state.value2 == ""
    with pytest.raises(AttributeError):
        test_state.invalid
    with pytest.raises(AttributeError):
        test_state.child_state.invalid
    with pytest.raises(AttributeError):
        test_state.child_state.grandchild_state.invalid


def test_set_child_attribute(test_state, child_state, grandchild_state):
    """Test setting the attribute of a state.

    Args:
        test_state: A state.
        child_state: A child state.
        grandchild_state: A grandchild state.
    """
    test_state.num1 = 10
    assert test_state.num1 == 10
    assert child_state.num1 == 10
    assert grandchild_state.num1 == 10

    grandchild_state.num1 = 5
    assert test_state.num1 == 5
    assert child_state.num1 == 5
    assert grandchild_state.num1 == 5

    child_state.value = "test"
    assert child_state.value == "test"
    assert grandchild_state.value == "test"

    grandchild_state.value = "test2"
    assert child_state.value == "test2"
    assert grandchild_state.value == "test2"

    grandchild_state.value2 = "test3"
    assert grandchild_state.value2 == "test3"


def test_get_substate(test_state, child_state, child_state2, grandchild_state):
    """Test getting the substate of a state.

    Args:
        test_state: A state.
        child_state: A child state.
        child_state2: A child state.
        grandchild_state: A grandchild state.
    """
    assert test_state.get_substate(("child_state",)) == child_state
    assert test_state.get_substate(("child_state2",)) == child_state2
    assert (
        test_state.get_substate(("child_state", "grandchild_state")) == grandchild_state
    )
    assert child_state.get_substate(("grandchild_state",)) == grandchild_state
    with pytest.raises(ValueError):
        test_state.get_substate(("invalid",))
    with pytest.raises(ValueError):
        test_state.get_substate(("child_state", "invalid"))
    with pytest.raises(ValueError):
        test_state.get_substate(("child_state", "grandchild_state", "invalid"))


def test_set_dirty_var(test_state):
    """Test changing state vars marks the value as dirty.

    Args:
        test_state: A state.
    """
    # Initially there should be no dirty vars.
    assert test_state.dirty_vars == set()

    # Setting a var should mark it as dirty.
    test_state.num1 = 1
    assert test_state.dirty_vars == {"num1", "sum"}

    # Setting another var should mark it as dirty.
    test_state.num2 = 2
    assert test_state.dirty_vars == {"num1", "num2", "sum"}

    # Cleaning the state should remove all dirty vars.
    test_state._clean()
    assert test_state.dirty_vars == set()


def test_set_dirty_substate(test_state, child_state, child_state2, grandchild_state):
    """Test changing substate vars marks the value as dirty.

    Args:
        test_state: A state.
        child_state: A child state.
        child_state2: A child state.
        grandchild_state: A grandchild state.
    """
    # Initially there should be no dirty vars.
    assert test_state.dirty_vars == set()
    assert child_state.dirty_vars == set()
    assert child_state2.dirty_vars == set()
    assert grandchild_state.dirty_vars == set()

    # Setting a var should mark it as dirty.
    child_state.value = "test"
    assert child_state.dirty_vars == {"value"}
    assert test_state.dirty_substates == {"child_state"}
    assert child_state.dirty_substates == set()

    # Cleaning the parent state should remove the dirty substate.
    test_state._clean()
    assert test_state.dirty_substates == set()
    assert child_state.dirty_vars == set()

    # Setting a var on the grandchild should bubble up.
    grandchild_state.value2 = "test2"
    assert child_state.dirty_substates == {"grandchild_state"}
    assert test_state.dirty_substates == {"child_state"}

    # Cleaning the middle state should keep the parent state dirty.
    child_state._clean()
    assert test_state.dirty_substates == {"child_state"}
    assert child_state.dirty_substates == set()
    assert grandchild_state.dirty_vars == set()


def test_reset(test_state, child_state):
    """Test resetting the state.

    Args:
        test_state: A state.
        child_state: A child state.
    """
    # Set some values.
    test_state.num1 = 1
    test_state.num2 = 2
    child_state.value = "test"

    # Reset the state.
    test_state.reset()

    # The values should be reset.
    assert test_state.num1 == 0
    assert test_state.num2 == 3.14
    assert child_state.value == ""

    expected_dirty_vars = {
        "num1",
        "num2",
        "obj",
        "upper",
        "complex",
        "is_hydrated",
        "fig",
        "key",
        "sum",
        "array",
        "map_key",
        "mapping",
        "dt",
    }

    # The dirty vars should be reset.
    assert test_state.dirty_vars == expected_dirty_vars
    assert child_state.dirty_vars == {"count", "value"}

    # The dirty substates should be reset.
    assert test_state.dirty_substates == {"child_state", "child_state2"}


@pytest.mark.asyncio
async def test_process_event_simple(test_state):
    """Test processing an event.

    Args:
        test_state: A state.
    """
    assert test_state.num1 == 0

    event = Event(token="t", name="set_num1", payload={"value": 69})
    update = await test_state._process(event).__anext__()

    # The event should update the value.
    assert test_state.num1 == 69

    # The delta should contain the changes, including computed vars.
    # assert update.delta == {"test_state": {"num1": 69, "sum": 72.14}}
    assert update.delta == {"test_state": {"num1": 69, "sum": 72.14, "upper": ""}}
    assert update.events == []


@pytest.mark.asyncio
async def test_process_event_substate(test_state, child_state, grandchild_state):
    """Test processing an event on a substate.

    Args:
        test_state: A state.
        child_state: A child state.
        grandchild_state: A grandchild state.
    """
    # Events should bubble down to the substate.
    assert child_state.value == ""
    assert child_state.count == 23
    event = Event(
        token="t", name="child_state.change_both", payload={"value": "hi", "count": 12}
    )
    update = await test_state._process(event).__anext__()
    assert child_state.value == "HI"
    assert child_state.count == 24
    assert update.delta == {
        "test_state": {"sum": 3.14, "upper": ""},
        "test_state.child_state": {"value": "HI", "count": 24},
    }
    test_state._clean()

    # Test with the granchild state.
    assert grandchild_state.value2 == ""
    event = Event(
        token="t",
        name="child_state.grandchild_state.set_value2",
        payload={"value": "new"},
    )
    update = await test_state._process(event).__anext__()
    assert grandchild_state.value2 == "new"
    assert update.delta == {
        "test_state": {"sum": 3.14, "upper": ""},
        "test_state.child_state.grandchild_state": {"value2": "new"},
    }


@pytest.mark.asyncio
async def test_process_event_generator():
    """Test event handlers that generate multiple updates."""
    gen_state = GenState()  # type: ignore
    event = Event(
        token="t",
        name="go",
        payload={"c": 5},
    )
    gen = gen_state._process(event)

    count = 0
    async for update in gen:
        count += 1
        if count == 6:
            assert update.delta == {}
            assert update.final
        else:
            assert gen_state.value == count
            assert update.delta == {
                "gen_state": {"value": count},
            }
            assert not update.final

    assert count == 6


def test_format_event_handler():
    """Test formatting an event handler."""
    assert (
        format.format_event_handler(TestState.do_something) == "test_state.do_something"  # type: ignore
    )
    assert (
        format.format_event_handler(ChildState.change_both)  # type: ignore
        == "test_state.child_state.change_both"
    )
    assert (
        format.format_event_handler(GrandchildState.do_nothing)  # type: ignore
        == "test_state.child_state.grandchild_state.do_nothing"
    )


def test_get_token(test_state, mocker, router_data):
    """Test that the token obtained from the router_data is correct.

    Args:
        test_state: The test state.
        mocker: Pytest Mocker object.
        router_data: The router data fixture.
    """
    mocker.patch.object(test_state, "router_data", router_data)

    assert test_state.get_token() == "b181904c-3953-4a79-dc18-ae9518c22f05"


def test_get_sid(test_state, mocker, router_data):
    """Test getting session id.

    Args:
        test_state: A state.
        mocker: Pytest Mocker object.
        router_data: The router data fixture.
    """
    mocker.patch.object(test_state, "router_data", router_data)

    assert test_state.get_sid() == "9fpxSzPb9aFMb4wFAAAH"


def test_get_headers(test_state, mocker, router_data, router_data_headers):
    """Test getting client headers.

    Args:
        test_state: A state.
        mocker: Pytest Mocker object.
        router_data: The router data fixture.
        router_data_headers: The expected headers.
    """
    mocker.patch.object(test_state, "router_data", router_data)

    assert test_state.get_headers() == router_data_headers


def test_get_client_ip(test_state, mocker, router_data):
    """Test getting client IP.

    Args:
        test_state: A state.
        mocker: Pytest Mocker object.
        router_data: The router data fixture.
    """
    mocker.patch.object(test_state, "router_data", router_data)

    assert test_state.get_client_ip() == "127.0.0.1"


def test_get_cookies(test_state, mocker, router_data):
    """Test getting client cookies.

    Args:
        test_state: A state.
        mocker: Pytest Mocker object.
        router_data: The router data fixture.
    """
    mocker.patch.object(test_state, "router_data", router_data)

    assert test_state.get_cookies() == {
        "csrftoken": "mocktoken",
        "name": "reflex",
        "list_cookies": ["some", "random", "cookies"],
        "dict_cookies": {"name": "reflex"},
        "val": True,
    }


def test_get_current_page(test_state):
    assert test_state.get_current_page() == ""

    route = "mypage/subpage"
    test_state.router_data = {RouteVar.PATH: route}

    assert test_state.get_current_page() == route


def test_get_query_params(test_state):
    assert test_state.get_query_params() == {}

    params = {"p1": "a", "p2": "b"}
    test_state.router_data = {RouteVar.QUERY: params}

    assert test_state.get_query_params() == params


def test_add_var():
    class DynamicState(State):
        pass

    ds1 = DynamicState()
    assert "dynamic_int" not in ds1.__dict__
    assert not hasattr(ds1, "dynamic_int")
    ds1.add_var("dynamic_int", int, 42)
    # Existing instances get the BaseVar
    assert ds1.dynamic_int.equals(DynamicState.dynamic_int)  # type: ignore
    # New instances get an actual value with the default
    assert DynamicState().dynamic_int == 42

    ds1.add_var("dynamic_list", List[int], [5, 10])
    assert ds1.dynamic_list.equals(DynamicState.dynamic_list)  # type: ignore
    ds2 = DynamicState()
    assert ds2.dynamic_list == [5, 10]
    ds2.dynamic_list.append(15)
    assert ds2.dynamic_list == [5, 10, 15]
    assert DynamicState().dynamic_list == [5, 10]

    ds1.add_var("dynamic_dict", Dict[str, int], {"k1": 5, "k2": 10})
    assert ds1.dynamic_dict.equals(DynamicState.dynamic_dict)  # type: ignore
    assert ds2.dynamic_dict.equals(DynamicState.dynamic_dict)  # type: ignore
    assert DynamicState().dynamic_dict == {"k1": 5, "k2": 10}
    assert DynamicState().dynamic_dict == {"k1": 5, "k2": 10}


def test_add_var_default_handlers(test_state):
    test_state.add_var("rand_int", int, 10)
    assert "set_rand_int" in test_state.event_handlers
    assert isinstance(test_state.event_handlers["set_rand_int"], EventHandler)


class InterdependentState(State):
    """A state with 3 vars and 3 computed vars.

    x: a variable that no computed var depends on
    v1: a varable that one computed var directly depeneds on
    _v2: a backend variable that one computed var directly depends on

    v1x2: a computed var that depends on v1
    v2x2: a computed var that depends on backend var _v2
    v1x2x2: a computed var that depends on computed var v1x2
    """

    x: int = 0
    v1: int = 0
    _v2: int = 1

    @rx.cached_var
    def v1x2(self) -> int:
        """Depends on var v1.

        Returns:
            Var v1 multiplied by 2
        """
        return self.v1 * 2

    @rx.cached_var
    def v2x2(self) -> int:
        """Depends on backend var _v2.

        Returns:
            backend var _v2 multiplied by 2
        """
        return self._v2 * 2

    @rx.cached_var
    def v1x2x2(self) -> int:
        """Depends on ComputedVar v1x2.

        Returns:
            ComputedVar v1x2 multiplied by 2
        """
        return self.v1x2 * 2


@pytest.fixture
def interdependent_state() -> State:
    """A state with varying dependency between vars.

    Returns:
        instance of InterdependentState
    """
    s = InterdependentState()
    s.dict()  # prime initial relationships by accessing all ComputedVars
    return s


def test_not_dirty_computed_var_from_var(interdependent_state):
    """Set Var that no ComputedVar depends on, expect no recalculation.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    interdependent_state.x = 5
    assert interdependent_state.get_delta() == {
        interdependent_state.get_full_name(): {"x": 5},
    }


def test_dirty_computed_var_from_var(interdependent_state):
    """Set Var that ComputedVar depends on, expect recalculation.

    The other ComputedVar depends on the changed ComputedVar and should also be
    recalculated. No other ComputedVars should be recalculated.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    interdependent_state.v1 = 1
    assert interdependent_state.get_delta() == {
        interdependent_state.get_full_name(): {"v1": 1, "v1x2": 2, "v1x2x2": 4},
    }


def test_dirty_computed_var_from_backend_var(interdependent_state):
    """Set backend var that ComputedVar depends on, expect recalculation.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    interdependent_state._v2 = 2
    assert interdependent_state.get_delta() == {
        interdependent_state.get_full_name(): {"v2x2": 4},
    }


def test_per_state_backend_var(interdependent_state):
    """Set backend var on one instance, expect no affect in other instances.

    Args:
        interdependent_state: A state with varying Var dependencies.
    """
    s2 = InterdependentState()
    assert s2._v2 == interdependent_state._v2
    interdependent_state._v2 = 2
    assert s2._v2 != interdependent_state._v2
    s3 = InterdependentState()
    assert s3._v2 != interdependent_state._v2
    # both s2 and s3 should still have the default value
    assert s2._v2 == s3._v2
    # changing s2._v2 should not affect others
    s2._v2 = 4
    assert s2._v2 != interdependent_state._v2
    assert s2._v2 != s3._v2


def test_child_state():
    """Test that the child state computed vars can reference parent state vars."""

    class MainState(State):
        v: int = 2

    class ChildState(MainState):
        @ComputedVar
        def rendered_var(self):
            return self.v

    ms = MainState()
    cs = ms.substates[ChildState.get_name()]
    assert ms.v == 2
    assert cs.v == 2
    assert cs.rendered_var == 2


def test_conditional_computed_vars():
    """Test that computed vars can have conditionals."""

    class MainState(State):
        flag: bool = False
        t1: str = "a"
        t2: str = "b"

        @ComputedVar
        def rendered_var(self) -> str:
            if self.flag:
                return self.t1
            return self.t2

    ms = MainState()
    # Initially there are no dirty computed vars.
    assert ms._dirty_computed_vars(from_vars={"flag"}) == {"rendered_var"}
    assert ms._dirty_computed_vars(from_vars={"t2"}) == {"rendered_var"}
    assert ms._dirty_computed_vars(from_vars={"t1"}) == {"rendered_var"}
    assert ms.computed_vars["rendered_var"].deps(objclass=MainState) == {
        "flag",
        "t1",
        "t2",
    }


def test_event_handlers_convert_to_fns(test_state, child_state):
    """Test that when the state is initialized, event handlers are converted to fns.

    Args:
        test_state: A state with event handlers.
        child_state: A child state with event handlers.
    """
    # The class instances should be event handlers.
    assert isinstance(TestState.do_something, EventHandler)
    assert isinstance(ChildState.change_both, EventHandler)

    # The object instances should be fns.
    test_state.do_something()

    child_state.change_both(value="goose", count=9)
    assert child_state.value == "GOOSE"
    assert child_state.count == 18


def test_event_handlers_call_other_handlers():
    """Test that event handlers can call other event handlers."""

    class MainState(State):
        v: int = 0

        def set_v(self, v: int):
            self.v = v

        def set_v2(self, v: int):
            self.set_v(v)

    class SubState(MainState):
        def set_v3(self, v: int):
            self.set_v2(v)

    ms = MainState()
    ms.set_v2(1)
    assert ms.v == 1

    # ensure handler can be called from substate
    ms.substates[SubState.get_name()].set_v3(2)
    assert ms.v == 2


def test_computed_var_cached():
    """Test that a ComputedVar doesn't recalculate when accessed."""
    comp_v_calls = 0

    class ComputedState(State):
        v: int = 0

        @rx.cached_var
        def comp_v(self) -> int:
            nonlocal comp_v_calls
            comp_v_calls += 1
            return self.v

    cs = ComputedState()
    assert cs.dict()["v"] == 0
    assert comp_v_calls == 1
    assert cs.dict()["comp_v"] == 0
    assert comp_v_calls == 1
    assert cs.comp_v == 0
    assert comp_v_calls == 1
    cs.v = 1
    assert comp_v_calls == 1
    assert cs.comp_v == 1
    assert comp_v_calls == 2


def test_computed_var_cached_depends_on_non_cached():
    """Test that a cached_var is recalculated if it depends on non-cached ComputedVar."""

    class ComputedState(State):
        v: int = 0

        @rx.var
        def no_cache_v(self) -> int:
            return self.v

        @rx.cached_var
        def dep_v(self) -> int:
            return self.no_cache_v

        @rx.cached_var
        def comp_v(self) -> int:
            return self.v

    cs = ComputedState()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 0, "dep_v": 0}}
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 0, "dep_v": 0}}
    cs._clean()
    assert cs.dirty_vars == set()
    cs.v = 1
    assert cs.dirty_vars == {"v", "comp_v", "dep_v", "no_cache_v"}
    assert cs.get_delta() == {
        cs.get_name(): {"v": 1, "no_cache_v": 1, "dep_v": 1, "comp_v": 1}
    }
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 1, "dep_v": 1}}
    cs._clean()
    assert cs.dirty_vars == set()
    assert cs.get_delta() == {cs.get_name(): {"no_cache_v": 1, "dep_v": 1}}
    cs._clean()
    assert cs.dirty_vars == set()


def test_computed_var_depends_on_parent_non_cached():
    """Child state cached_var that depends on parent state un cached var is always recalculated."""
    counter = 0

    class ParentState(State):
        @rx.var
        def no_cache_v(self) -> int:
            nonlocal counter
            counter += 1
            return counter

    class ChildState(ParentState):
        @rx.cached_var
        def dep_v(self) -> int:
            return self.no_cache_v

    ps = ParentState()
    cs = ps.substates[ChildState.get_name()]

    assert ps.dirty_vars == set()
    assert cs.dirty_vars == set()

    assert ps.dict() == {
        cs.get_name(): {"dep_v": 2},
        "no_cache_v": 1,
        IS_HYDRATED: False,
    }
    assert ps.dict() == {
        cs.get_name(): {"dep_v": 4},
        "no_cache_v": 3,
        IS_HYDRATED: False,
    }
    assert ps.dict() == {
        cs.get_name(): {"dep_v": 6},
        "no_cache_v": 5,
        IS_HYDRATED: False,
    }
    assert counter == 6


@pytest.mark.parametrize("use_partial", [True, False])
def test_cached_var_depends_on_event_handler(use_partial: bool):
    """A cached_var that calls an event handler calculates deps correctly.

    Args:
        use_partial: if true, replace the EventHandler with functools.partial
    """
    counter = 0

    class HandlerState(State):
        x: int = 42

        def handler(self):
            self.x = self.x + 1

        @rx.cached_var
        def cached_x_side_effect(self) -> int:
            self.handler()
            nonlocal counter
            counter += 1
            return counter

    if use_partial:
        HandlerState.handler = functools.partial(HandlerState.handler.fn)
        assert isinstance(HandlerState.handler, functools.partial)
    else:
        assert isinstance(HandlerState.handler, EventHandler)

    s = HandlerState()
    assert "cached_x_side_effect" in s.computed_var_dependencies["x"]
    assert s.cached_x_side_effect == 1
    assert s.x == 43
    s.handler()
    assert s.cached_x_side_effect == 2
    assert s.x == 45


def test_computed_var_dependencies():
    """Test that a ComputedVar correctly tracks its dependencies."""

    class ComputedState(State):
        v: int = 0
        w: int = 0
        x: int = 0
        y: List[int] = [1, 2, 3]
        _z: List[int] = [1, 2, 3]

        @rx.cached_var
        def comp_v(self) -> int:
            """Direct access.

            Returns:
                The value of self.v.
            """
            return self.v

        @rx.cached_var
        def comp_w(self):
            """Nested lambda.

            Returns:
                A lambda that returns the value of self.w.
            """
            return lambda: self.w

        @rx.cached_var
        def comp_x(self):
            """Nested function.

            Returns:
                A function that returns the value of self.x.
            """

            def _():
                return self.x

            return _

        @rx.cached_var
        def comp_y(self) -> List[int]:
            """Comprehension iterating over attribute.

            Returns:
                A list of the values of self.y.
            """
            return [round(y) for y in self.y]

        @rx.cached_var
        def comp_z(self) -> List[bool]:
            """Comprehension accesses attribute.

            Returns:
                A list of whether the values 0-4 are in self._z.
            """
            return [z in self._z for z in range(5)]

    cs = ComputedState()
    assert cs.computed_var_dependencies["v"] == {"comp_v"}
    assert cs.computed_var_dependencies["w"] == {"comp_w"}
    assert cs.computed_var_dependencies["x"] == {"comp_x"}
    assert cs.computed_var_dependencies["y"] == {"comp_y"}
    assert cs.computed_var_dependencies["_z"] == {"comp_z"}


def test_backend_method():
    """A method with leading underscore should be callable from event handler."""

    class BackendMethodState(State):
        def _be_method(self):
            return True

        def handler(self):
            assert self._be_method()

    bms = BackendMethodState()
    bms.handler()
    assert bms._be_method()


def test_setattr_of_mutable_types(mutable_state):
    """Test that mutable types are converted to corresponding Reflex wrappers.

    Args:
        mutable_state: A test state.
    """
    array = mutable_state.array
    hashmap = mutable_state.hashmap
    test_set = mutable_state.test_set

    assert isinstance(array, ReflexList)
    assert isinstance(array[1], ReflexList)
    assert isinstance(array[2], ReflexDict)

    assert isinstance(hashmap, ReflexDict)
    assert isinstance(hashmap["key"], ReflexList)
    assert isinstance(hashmap["third_key"], ReflexDict)

    assert isinstance(test_set, set)

    mutable_state.reassign_mutables()

    array = mutable_state.array
    hashmap = mutable_state.hashmap
    test_set = mutable_state.test_set

    assert isinstance(array, ReflexList)
    assert isinstance(array[1], ReflexList)
    assert isinstance(array[2], ReflexDict)

    assert isinstance(hashmap, ReflexDict)
    assert isinstance(hashmap["mod_key"], ReflexList)
    assert isinstance(hashmap["mod_third_key"], ReflexDict)

    assert isinstance(test_set, ReflexSet)


def test_error_on_state_method_shadow():
    """Test that an error is thrown when an event handler shadows a state method."""
    with pytest.raises(NameError) as err:

        class InvalidTest(rx.State):
            def reset(self):
                pass

    assert (
        err.value.args[0]
        == f"The event handler name `reset` shadows a builtin State method; use a different name instead"
    )


def test_state_with_invalid_yield():
    """Test that an error is thrown when a state yields an invalid value."""

    class StateWithInvalidYield(rx.State):
        """A state that yields an invalid value."""

        def invalid_handler(self):
            """Invalid handler.

            Yields:
                an invalid value.
            """
            yield 1

    invalid_state = StateWithInvalidYield()
    with pytest.raises(TypeError) as err:
        invalid_state._check_valid(
            invalid_state.event_handlers["invalid_handler"],
            rx.event.Event(token="fake_token", name="invalid_handler"),
        )
    assert (
        "must only return/yield: None, Events or other EventHandlers"
        in err.value.args[0]
    )


@pytest.fixture(scope="function", params=["in_process", "redis"])
def state_manager(request):
    """Instance of state manager parametrized for redis and in-process.

    Args:
        request: pytest request object.

    Returns:
        A state manager instance
    """
    state_manager = StateManager()
    state_manager.setup(TestState)
    assert not state_manager._states_locks

    if request.param == "redis":
        if state_manager.redis is None:
            pytest.skip("Test requires redis")
    else:
        # explicitly NOT using redis
        state_manager.redis = None

    return state_manager


@pytest.mark.asyncio
async def test_state_manager_modify_state(state_manager: StateManager, token: str):
    """Test that the state manager can modify a state exclusively.

    Args:
        state_manager: A state manager instance.
        token: A token.
    """
    async with state_manager.modify_state(token):
        if state_manager.redis is None:
            assert token in state_manager._states_locks
            assert state_manager._states_locks[token].locked()
        else:
            assert await state_manager.redis.get(f"{token}_lock")
    # lock should be dropped after exiting the context
    if state_manager.redis is None:
        assert not state_manager._states_locks[token].locked()
    else:
        assert (await state_manager.redis.get(f"{token}_lock")) is None

    # separate instances should NOT share locks
    sm2 = StateManager()
    assert sm2._state_manager_lock is state_manager._state_manager_lock
    assert not sm2._states_locks
    if state_manager._states_locks:
        assert sm2._states_locks != state_manager._states_locks


@pytest.mark.asyncio
async def test_state_manager_contend(state_manager: StateManager, token: str):
    """Multiple coroutines attempting to access the same state.

    Args:
        state_manager: A state manager instance.
        token: A token.
    """
    n_coroutines = 10
    exp_num1 = 10

    async with state_manager.modify_state(token) as state:
        state.num1 = 0

    async def _coro():
        async with state_manager.modify_state(token) as state:
            await asyncio.sleep(0.01)
            state.num1 += 1

    tasks = [asyncio.create_task(_coro()) for _ in range(n_coroutines)]

    for f in asyncio.as_completed(tasks):
        await f

    assert (await state_manager.get_state(token)).num1 == exp_num1

    if state_manager.redis is None:
        assert token in state_manager._states_locks
        assert not state_manager._states_locks[token].locked()
    else:
        assert (await state_manager.redis.get(f"{token}_lock")) is None


@pytest.mark.asyncio
async def test_state_manager_lock_expire(token):
    """Test that the state manager lock expires and raises exception exiting context.

    Args:
        token: A token.
    """
    state_manager = StateManager()
    state_manager.setup(TestState)
    if state_manager.redis is None:
        pytest.skip("Test requires redis")
    state_manager.lock_expiration = LOCK_EXPIRATION

    async with state_manager.modify_state(token):
        await asyncio.sleep(0.01)

    with pytest.raises(LockExpiredError):
        async with state_manager.modify_state(token):
            await asyncio.sleep(LOCK_EXPIRE_SLEEP)


@pytest.mark.asyncio
async def test_state_manager_lock_expire_contend(token: str):
    """Test that the state manager lock expires and queued waiters proceed.

    Args:
        token: A token.
    """
    exp_num1 = 4252
    unexp_num1 = 666

    state_manager = StateManager()
    state_manager.setup(TestState)
    if state_manager.redis is None:
        pytest.skip("Test requires redis")
    state_manager.lock_expiration = LOCK_EXPIRATION

    order = []

    async def _coro_blocker():
        async with state_manager.modify_state(token) as state:
            order.append("blocker")
            await asyncio.sleep(LOCK_EXPIRE_SLEEP)
            state.num1 = unexp_num1

    async def _coro_waiter():
        while "blocker" not in order:
            await asyncio.sleep(0.005)
        async with state_manager.modify_state(token) as state:
            order.append("waiter")
            assert state.num1 != unexp_num1
            state.num1 = exp_num1

    tasks = [
        asyncio.create_task(_coro_blocker()),
        asyncio.create_task(_coro_waiter()),
    ]
    with pytest.raises(LockExpiredError):
        await tasks[0]
    await tasks[1]

    assert order == ["blocker", "waiter"]
    assert (await state_manager.get_state(token)).num1 == exp_num1


@pytest.fixture(scope="function")
def mock_app(monkeypatch, app: rx.App, state_manager: StateManager) -> rx.App:
    """Mock app fixture.

    Args:
        monkeypatch: Pytest monkeypatch object.
        app: An app.
        state_manager: A state manager.

    Returns:
        The app, after mocking out prerequisites.get_app()
    """
    app_module = Mock()
    setattr(app_module, APP_VAR, app)
    app.state = TestState
    app.state_manager = state_manager
    assert app.event_namespace is not None
    app.event_namespace.emit = AsyncMock()
    monkeypatch.setattr(prerequisites, "get_app", lambda: app_module)
    return app


@pytest.mark.asyncio
async def test_state_proxy(grandchild_state: GrandchildState, mock_app: rx.App):
    """Test that the state proxy works.

    Args:
        grandchild_state: A grandchild state.
        mock_app: An app that will be returned by `get_app()`
    """
    child_state = grandchild_state.parent_state
    assert child_state is not None
    parent_state = child_state.parent_state
    assert parent_state is not None
    if mock_app.state_manager.redis is None:
        mock_app.state_manager.states[parent_state.get_token()] = parent_state

    sp = StateProxy(grandchild_state)
    assert sp._state_instance == grandchild_state
    assert sp._substate_path == grandchild_state.get_full_name().split(".")
    assert sp._app is mock_app
    assert not sp._mutable
    assert sp._actx is None

    # cannot use normal contextmanager protocol
    with pytest.raises(TypeError), sp:
        pass

    with pytest.raises(ImmutableStateError):
        # cannot directly modify state proxy outside of async context
        sp.value2 = 16

    async with sp:
        assert sp._actx is not None
        assert sp._mutable  # proxy is mutable inside context
        if mock_app.state_manager.redis is None:
            # For in-process store, only one instance of the state exists
            assert sp._state_instance is grandchild_state
        else:
            # When redis is used, a new+updated instance is assigned to the proxy
            assert sp._state_instance is not grandchild_state
        sp.value2 = 42
    assert not sp._mutable  # proxy is not mutable after exiting context
    assert sp._actx is None
    assert sp.value2 == 42

    # Get the state from the state manager directly and check that the value is updated
    gotten_state = await mock_app.state_manager.get_state(grandchild_state.get_token())
    if mock_app.state_manager.redis is None:
        # For in-process store, only one instance of the state exists
        assert gotten_state is parent_state
    else:
        assert gotten_state is not parent_state
    gotten_grandchild_state = gotten_state.get_substate(sp._substate_path)
    assert gotten_grandchild_state is not None
    assert gotten_grandchild_state.value2 == 42

    # ensure state update was emitted
    assert mock_app.event_namespace is not None
    mock_app.event_namespace.emit.assert_called_once_with(
        str(SocketEvent.EVENT),
        StateUpdate(
            delta={
                parent_state.get_full_name(): {
                    "upper": "",
                    "sum": 3.14,
                },
                grandchild_state.get_full_name(): {
                    "value2": 42,
                },
            }
        ).json(),
        to=grandchild_state.get_sid(),
    )
