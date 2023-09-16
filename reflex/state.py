"""Define the reflex state specification."""
from __future__ import annotations

import asyncio
import copy
import functools
import inspect
import json
import traceback
import urllib.parse
from abc import ABC
from collections import defaultdict
from types import FunctionType
from typing import (
    Any,
    AsyncIterator,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Type,
)

import cloudpickle
import pydantic
import wrapt
from redis import Redis

from reflex import constants
from reflex.base import Base
from reflex.event import Event, EventHandler, EventSpec, fix_events, window_alert
from reflex.utils import format, prerequisites, types
from reflex.vars import BaseVar, ComputedVar, Var

Delta = Dict[str, Any]


class State(Base, ABC, extra=pydantic.Extra.allow):
    """The state of the app."""

    # A map from the var name to the var.
    vars: ClassVar[Dict[str, Var]] = {}

    # The base vars of the class.
    base_vars: ClassVar[Dict[str, BaseVar]] = {}

    # The computed vars of the class.
    computed_vars: ClassVar[Dict[str, ComputedVar]] = {}

    # Vars inherited by the parent state.
    inherited_vars: ClassVar[Dict[str, Var]] = {}

    # Backend vars that are never sent to the client.
    backend_vars: ClassVar[Dict[str, Any]] = {}

    # Backend vars inherited
    inherited_backend_vars: ClassVar[Dict[str, Any]] = {}

    # The event handlers.
    event_handlers: ClassVar[Dict[str, EventHandler]] = {}

    # The parent state.
    parent_state: Optional[State] = None

    # The substates of the state.
    substates: Dict[str, State] = {}

    # The set of dirty vars.
    dirty_vars: Set[str] = set()

    # The set of dirty substates.
    dirty_substates: Set[str] = set()

    # The routing path that triggered the state
    router_data: Dict[str, Any] = {}

    # Mapping of var name to set of computed variables that depend on it
    computed_var_dependencies: Dict[str, Set[str]] = {}

    # Mapping of var name to set of substates that depend on it
    substate_var_dependencies: Dict[str, Set[str]] = {}

    # Per-instance copy of backend variable values
    _backend_vars: Dict[str, Any] = {}

    def __init__(self, *args, parent_state: State | None = None, **kwargs):
        """Initialize the state.

        Args:
            *args: The args to pass to the Pydantic init method.
            parent_state: The parent state.
            **kwargs: The kwargs to pass to the Pydantic init method.
        """
        kwargs["parent_state"] = parent_state
        super().__init__(*args, **kwargs)

        # initialize per-instance var dependency tracking
        self.computed_var_dependencies = defaultdict(set)
        self.substate_var_dependencies = defaultdict(set)

        # Setup the substates.
        for substate in self.get_substates():
            self.substates[substate.get_name()] = substate(parent_state=self)
        # Convert the event handlers to functions.
        self._init_event_handlers()

        # Initialize computed vars dependencies.
        inherited_vars = set(self.inherited_vars).union(
            set(self.inherited_backend_vars),
        )
        for cvar_name, cvar in self.computed_vars.items():
            # Add the dependencies.
            for var in cvar.deps(objclass=type(self)):
                self.computed_var_dependencies[var].add(cvar_name)
                if var in inherited_vars:
                    # track that this substate depends on its parent for this var
                    state_name = self.get_name()
                    parent_state = self.parent_state
                    while parent_state is not None and var in parent_state.vars:
                        parent_state.substate_var_dependencies[var].add(state_name)
                        state_name, parent_state = (
                            parent_state.get_name(),
                            parent_state.parent_state,
                        )

        # Create a fresh copy of the backend variables for this instance
        self._backend_vars = copy.deepcopy(self.backend_vars)

    def _init_event_handlers(self, state: State | None = None):
        """Initialize event handlers.

        Allow event handlers to be called directly on the instance. This is
        called recursively for all parent states.

        Args:
            state: The state to initialize the event handlers on.
        """
        if state is None:
            state = self

        # Convert the event handlers to functions.
        for name, event_handler in state.event_handlers.items():
            fn = functools.partial(event_handler.fn, self)
            fn.__module__ = event_handler.fn.__module__  # type: ignore
            fn.__qualname__ = event_handler.fn.__qualname__  # type: ignore
            setattr(self, name, fn)

        # Also allow direct calling of parent state event handlers
        if state.parent_state is not None:
            self._init_event_handlers(state.parent_state)

    def __repr__(self) -> str:
        """Get the string representation of the state.

        Returns:
            The string representation of the state.
        """
        return f"{self.__class__.__name__}({self.dict()})"

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Do some magic for the subclass initialization.

        Args:
            **kwargs: The kwargs to pass to the pydantic init_subclass method.
        """
        super().__init_subclass__(**kwargs)
        # Event handlers should not shadow builtin state methods.
        cls._check_overridden_methods()

        # Get the parent vars.
        parent_state = cls.get_parent_state()
        if parent_state is not None:
            cls.inherited_vars = parent_state.vars
            cls.inherited_backend_vars = parent_state.backend_vars

        cls.new_backend_vars = {
            name: value
            for name, value in cls.__dict__.items()
            if types.is_backend_variable(name)
            and name not in cls.inherited_backend_vars
            and not isinstance(value, FunctionType)
        }

        cls.backend_vars = {**cls.inherited_backend_vars, **cls.new_backend_vars}

        # Set the base and computed vars.
        cls.base_vars = {
            f.name: BaseVar(name=f.name, type_=f.outer_type_).set_state(cls)
            for f in cls.get_fields().values()
            if f.name not in cls.get_skip_vars()
        }
        cls.computed_vars = {
            v.name: v.set_state(cls)
            for v in cls.__dict__.values()
            if isinstance(v, ComputedVar)
        }
        cls.vars = {
            **cls.inherited_vars,
            **cls.base_vars,
            **cls.computed_vars,
        }
        cls.event_handlers = {}

        # Setup the base vars at the class level.
        for prop in cls.base_vars.values():
            cls._init_var(prop)

        # Set up the event handlers.
        events = {
            name: fn
            for name, fn in cls.__dict__.items()
            if not name.startswith("_")
            and isinstance(fn, Callable)
            and not isinstance(fn, EventHandler)
        }
        for name, fn in events.items():
            handler = EventHandler(fn=fn)
            cls.event_handlers[name] = handler
            setattr(cls, name, handler)

    @classmethod
    def _check_overridden_methods(cls):
        """Check for shadow methods and raise error if any.

        Raises:
            NameError: When an event handler shadows an inbuilt state method.
        """
        overridden_methods = set()
        state_base_functions = cls._get_base_functions()
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            # Check if the method is overridden and not a dunder method
            if (
                not name.startswith("__")
                and method.__name__ in state_base_functions
                and state_base_functions[method.__name__] != method
            ):
                overridden_methods.add(method.__name__)

        for method_name in overridden_methods:
            raise NameError(
                f"The event handler name `{method_name}` shadows a builtin State method; use a different name instead"
            )

    @classmethod
    def get_skip_vars(cls) -> set[str]:
        """Get the vars to skip when serializing.

        Returns:
            The vars to skip when serializing.
        """
        return set(cls.inherited_vars) | {
            "parent_state",
            "substates",
            "dirty_vars",
            "dirty_substates",
            "router_data",
            "computed_var_dependencies",
            "substate_var_dependencies",
            "_backend_vars",
        }

    @classmethod
    @functools.lru_cache()
    def get_parent_state(cls) -> Type[State] | None:
        """Get the parent state.

        Returns:
            The parent state.
        """
        parent_states = [
            base
            for base in cls.__bases__
            if types._issubclass(base, State) and base is not State
        ]
        assert len(parent_states) < 2, "Only one parent state is allowed."
        return parent_states[0] if len(parent_states) == 1 else None  # type: ignore

    @classmethod
    @functools.lru_cache()
    def get_substates(cls) -> set[Type[State]]:
        """Get the substates of the state.

        Returns:
            The substates of the state.
        """
        return set(cls.__subclasses__())

    @classmethod
    @functools.lru_cache()
    def get_name(cls) -> str:
        """Get the name of the state.

        Returns:
            The name of the state.
        """
        return format.to_snake_case(cls.__name__)

    @classmethod
    @functools.lru_cache()
    def get_full_name(cls) -> str:
        """Get the full name of the state.

        Returns:
            The full name of the state.
        """
        name = cls.get_name()
        parent_state = cls.get_parent_state()
        if parent_state is not None:
            name = ".".join((parent_state.get_full_name(), name))
        return name

    @classmethod
    @functools.lru_cache()
    def get_class_substate(cls, path: Sequence[str]) -> Type[State]:
        """Get the class substate.

        Args:
            path: The path to the substate.

        Returns:
            The class substate.

        Raises:
            ValueError: If the substate is not found.
        """
        if len(path) == 0:
            return cls
        if path[0] == cls.get_name():
            if len(path) == 1:
                return cls
            path = path[1:]
        for substate in cls.get_substates():
            if path[0] == substate.get_name():
                return substate.get_class_substate(path[1:])
        raise ValueError(f"Invalid path: {path}")

    @classmethod
    def get_class_var(cls, path: Sequence[str]) -> Any:
        """Get the class var.

        Args:
            path: The path to the var.

        Returns:
            The class var.

        Raises:
            ValueError: If the path is invalid.
        """
        path, name = path[:-1], path[-1]
        substate = cls.get_class_substate(tuple(path))
        if not hasattr(substate, name):
            raise ValueError(f"Invalid path: {path}")
        return getattr(substate, name)

    @classmethod
    def _init_var(cls, prop: BaseVar):
        """Initialize a variable.

        Args:
            prop: The variable to initialize

        Raises:
            TypeError: if the variable has an incorrect type
        """
        if not types.is_valid_var_type(prop.type_):
            raise TypeError(
                "State vars must be primitive Python types, "
                "Plotly figures, Pandas dataframes, "
                "or subclasses of rx.Base. "
                f'Found var "{prop.name}" with type {prop.type_}.'
            )
        cls._set_var(prop)
        cls._create_setter(prop)
        cls._set_default_value(prop)

    @classmethod
    def add_var(cls, name: str, type_: Any, default_value: Any = None):
        """Add dynamically a variable to the State.

        The variable added this way can be used in the same way as a variable
        defined statically in the model.

        Args:
            name: The name of the variable
            type_: The type of the variable
            default_value: The default value of the variable

        Raises:
            NameError: if a variable of this name already exists
        """
        if name in cls.__fields__:
            raise NameError(
                f"The variable '{name}' already exist. Use a different name"
            )

        # create the variable based on name and type
        var = BaseVar(name=name, type_=type_)
        var.set_state(cls)

        # add the pydantic field dynamically (must be done before _init_var)
        cls.add_field(var, default_value)

        cls._init_var(var)

        # update the internal dicts so the new variable is correctly handled
        cls.base_vars.update({name: var})
        cls.vars.update({name: var})

        # let substates know about the new variable
        for substate_class in cls.__subclasses__():
            substate_class.vars.setdefault(name, var)

    @classmethod
    def _set_var(cls, prop: BaseVar):
        """Set the var as a class member.

        Args:
            prop: The var instance to set.
        """
        setattr(cls, prop.name, prop)

    @classmethod
    def _create_setter(cls, prop: BaseVar):
        """Create a setter for the var.

        Args:
            prop: The var to create a setter for.
        """
        setter_name = prop.get_setter_name(include_state=False)
        if setter_name not in cls.__dict__:
            event_handler = EventHandler(fn=prop.get_setter())
            cls.event_handlers[setter_name] = event_handler
            setattr(cls, setter_name, event_handler)

    @classmethod
    def _set_default_value(cls, prop: BaseVar):
        """Set the default value for the var.

        Args:
            prop: The var to set the default value for.
        """
        # Get the pydantic field for the var.
        field = cls.get_fields()[prop.name]
        default_value = prop.get_default_value()
        if field.required and default_value is not None:
            field.required = False
            field.default = default_value

    @staticmethod
    def _get_base_functions() -> dict[str, FunctionType]:
        """Get all functions of the state class excluding dunder methods.

        Returns:
            The functions of rx.State class as a dict.
        """
        return {
            func[0]: func[1]
            for func in inspect.getmembers(State, predicate=inspect.isfunction)
            if not func[0].startswith("__")
        }

    def get_token(self) -> str:
        """Return the token of the client associated with this state.

        Returns:
            The token of the client.
        """
        return self.router_data.get(constants.RouteVar.CLIENT_TOKEN, "")

    def get_sid(self) -> str:
        """Return the session ID of the client associated with this state.

        Returns:
            The session ID of the client.
        """
        return self.router_data.get(constants.RouteVar.SESSION_ID, "")

    def get_headers(self) -> Dict:
        """Return the headers of the client associated with this state.

        Returns:
            The headers of the client.
        """
        return self.router_data.get(constants.RouteVar.HEADERS, {})

    def get_client_ip(self) -> str:
        """Return the IP of the client associated with this state.

        Returns:
            The IP of the client.
        """
        return self.router_data.get(constants.RouteVar.CLIENT_IP, "")

    def get_current_page(self, origin=False) -> str:
        """Obtain the path of current page from the router data.

        Args:
            origin: whether to return the base route as shown in browser

        Returns:
            The current page.
        """
        if origin:
            return self.router_data.get(constants.RouteVar.ORIGIN, "")
        else:
            return self.router_data.get(constants.RouteVar.PATH, "")

    def get_query_params(self) -> dict[str, str]:
        """Obtain the query parameters for the queried page.

        The query object contains both the URI parameters and the GET parameters.

        Returns:
            The dict of query parameters.
        """
        return self.router_data.get(constants.RouteVar.QUERY, {})

    def get_cookies(self) -> dict[str, str]:
        """Obtain the cookies of the client stored in the browser.

        Returns:
                The dict of cookies.
        """
        cookie_dict = {}
        cookies = self.get_headers().get(constants.RouteVar.COOKIE, "").split(";")

        cookie_pairs = [cookie.split("=") for cookie in cookies if cookie]

        for pair in cookie_pairs:
            key, value = pair[0].strip(), urllib.parse.unquote(pair[1].strip())
            try:
                # cast non-string values to the actual types.
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
            finally:
                cookie_dict[key] = value
        return cookie_dict

    @classmethod
    def setup_dynamic_args(cls, args: dict[str, str]):
        """Set up args for easy access in renderer.

        Args:
            args: a dict of args
        """

        def argsingle_factory(param):
            @ComputedVar
            def inner_func(self) -> str:
                return self.get_query_params().get(param, "")

            return inner_func

        def arglist_factory(param):
            @ComputedVar
            def inner_func(self) -> List:
                return self.get_query_params().get(param, [])

            return inner_func

        for param, value in args.items():
            if value == constants.RouteArgType.SINGLE:
                func = argsingle_factory(param)
            elif value == constants.RouteArgType.LIST:
                func = arglist_factory(param)
            else:
                continue
            func.fget.__name__ = param  # to allow passing as a prop # type: ignore
            cls.vars[param] = cls.computed_vars[param] = func.set_state(cls)  # type: ignore
            setattr(cls, param, func)

    def __getattribute__(self, name: str) -> Any:
        """Get the state var.

        If the var is inherited, get the var from the parent state.

        Args:
            name: The name of the var.

        Returns:
            The value of the var.
        """
        # If the state hasn't been initialized yet, return the default value.
        if not super().__getattribute__("__dict__"):
            return super().__getattribute__(name)

        inherited_vars = {
            **super().__getattribute__("inherited_vars"),
            **super().__getattribute__("inherited_backend_vars"),
        }
        if name in inherited_vars:
            return getattr(super().__getattribute__("parent_state"), name)
        elif name in super().__getattribute__("_backend_vars"):
            value = super().__getattribute__("_backend_vars").__getitem__(name)
        else:
            value = super().__getattribute__(name)
        if isinstance(
            value, MutableProxy.__mutable_types__
        ) and name in super().__getattribute__("base_vars"):
            # track changes in mutable containers (list, dict, set, etc)
            return MutableProxy(value, self, name)
        return value

    def __setattr__(self, name: str, value: Any):
        """Set the attribute.

        If the attribute is inherited, set the attribute on the parent state.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.
        """
        if isinstance(value, MutableProxy):
            # unwrap proxy objects when assigning back to the state
            value = value.__wrapped__

        # Set the var on the parent state.
        inherited_vars = {**self.inherited_vars, **self.inherited_backend_vars}
        if name in inherited_vars:
            setattr(self.parent_state, name, value)
            return

        if types.is_backend_variable(name) and name != "_backend_vars":
            self._backend_vars.__setitem__(name, value)
            self.dirty_vars.add(name)
            self._mark_dirty()
            return

        # Set the attribute.
        super().__setattr__(name, value)

        # Add the var to the dirty list.
        if name in self.vars or name in self.computed_var_dependencies:
            self.dirty_vars.add(name)
            self._mark_dirty()

        # For now, handle router_data updates as a special case
        if name == constants.ROUTER_DATA:
            self.dirty_vars.add(name)
            self._mark_dirty()
            # propagate router_data updates down the state tree
            for substate in self.substates.values():
                setattr(substate, name, value)

    def reset(self):
        """Reset all the base vars to their default values."""
        # Reset the base vars.
        fields = self.get_fields()
        for prop_name in self.base_vars:
            setattr(self, prop_name, fields[prop_name].default)

        # Recursively reset the substates.
        for substate in self.substates.values():
            substate.reset()

    def _reset_client_storage(self):
        """Reset client storage base vars to their default values."""
        # Client-side storage is reset during hydrate so that clearing cookies
        # on the browser also resets the values on the backend.
        fields = self.get_fields()
        for prop_name in self.base_vars:
            field = fields[prop_name]
            if isinstance(field.default, ClientStorageBase) or (
                isinstance(field.type_, type)
                and issubclass(field.type_, ClientStorageBase)
            ):
                setattr(self, prop_name, field.default)

        # Recursively reset the substate client storage.
        for substate in self.substates.values():
            substate._reset_client_storage()

    def get_substate(self, path: Sequence[str]) -> State | None:
        """Get the substate.

        Args:
            path: The path to the substate.

        Returns:
            The substate.

        Raises:
            ValueError: If the substate is not found.
        """
        if len(path) == 0:
            return self
        if path[0] == self.get_name():
            if len(path) == 1:
                return self
            path = path[1:]
        if path[0] not in self.substates:
            raise ValueError(f"Invalid path: {path}")
        return self.substates[path[0]].get_substate(path[1:])

    async def _process(self, event: Event) -> AsyncIterator[StateUpdate]:
        """Obtain event info and process event.

        Args:
            event: The event to process.

        Yields:
            The state update after processing the event.

        Raises:
            ValueError: If the state value is None.
        """
        # Get the event handler.
        path = event.name.split(".")
        path, name = path[:-1], path[-1]
        substate = self.get_substate(path)
        handler = substate.event_handlers[name]  # type: ignore

        if not substate:
            raise ValueError(
                "The value of state cannot be None when processing an event."
            )

        # Get the event generator.
        event_iter = self._process_event(
            handler=handler,
            state=substate,
            payload=event.payload,
        )

        # Clean the state before processing the event.
        self._clean()

        # Run the event generator and return state updates.
        async for events, final in event_iter:
            # Fix the returned events.
            events = fix_events(events, event.token)  # type: ignore

            # Get the delta after processing the event.
            delta = self.get_delta()

            # Yield the state update.
            yield StateUpdate(delta=delta, events=events, final=final)

            # Clean the state to prepare for the next event.
            self._clean()

    def _check_valid(self, handler: EventHandler, events: Any) -> Any:
        """Check if the events yielded are valid. They must be EventHandlers or EventSpecs.

        Args:
            handler: EventHandler.
            events: The events to be checked.

        Raises:
            TypeError: If any of the events are not valid.

        Returns:
            The events as they are if valid.
        """

        def _is_valid_type(events: Any) -> bool:
            return isinstance(events, (EventHandler, EventSpec))

        if events is None or _is_valid_type(events):
            return events
        try:
            if all(_is_valid_type(e) for e in events):
                return events
        except TypeError:
            pass

        raise TypeError(
            f"Your handler {handler.fn.__qualname__} must only return/yield: None, Events or other EventHandlers referenced by their class (not using `self`)"
        )

    async def _process_event(
        self, handler: EventHandler, state: State, payload: Dict
    ) -> AsyncIterator[tuple[list[EventSpec] | None, bool]]:
        """Process event.

        Args:
            handler: EventHandler to process.
            state: State to process the handler.
            payload: The event payload.

        Yields:
            Tuple containing:
                0: The state update after processing the event.
                1: Whether the event is the final event.
        """
        # Get the function to process the event.
        fn = functools.partial(handler.fn, state)

        # Wrap the function in a try/except block.
        try:
            # Handle async functions.
            if asyncio.iscoroutinefunction(fn.func):
                events = await fn(**payload)

            # Handle regular functions.
            else:
                events = fn(**payload)
            # Handle async generators.
            if inspect.isasyncgen(events):
                async for event in events:
                    yield self._check_valid(handler, event), False
                yield None, True

            # Handle regular generators.
            elif inspect.isgenerator(events):
                try:
                    while True:
                        yield self._check_valid(handler, next(events)), False
                except StopIteration as si:
                    # the "return" value of the generator is not available
                    # in the loop, we must catch StopIteration to access it
                    if si.value is not None:
                        yield self._check_valid(handler, si.value), False
                yield None, True

            # Handle regular event chains.
            else:
                yield self._check_valid(handler, events), True

        # If an error occurs, throw a window alert.
        except Exception:
            error = traceback.format_exc()
            print(error)
            yield [window_alert("An error occurred. See logs for details.")], True

    def _always_dirty_computed_vars(self) -> set[str]:
        """The set of ComputedVars that always need to be recalculated.

        Returns:
            Set of all ComputedVar in this state where cache=False
        """
        return set(
            cvar_name
            for cvar_name, cvar in self.computed_vars.items()
            if not cvar.cache
        )

    def _mark_dirty_computed_vars(self) -> None:
        """Mark ComputedVars that need to be recalculated based on dirty_vars."""
        dirty_vars = self.dirty_vars
        while dirty_vars:
            calc_vars, dirty_vars = dirty_vars, set()
            for cvar in self._dirty_computed_vars(from_vars=calc_vars):
                self.dirty_vars.add(cvar)
                dirty_vars.add(cvar)
                actual_var = self.computed_vars.get(cvar)
                if actual_var is not None:
                    actual_var.mark_dirty(instance=self)

    def _dirty_computed_vars(self, from_vars: set[str] | None = None) -> set[str]:
        """Determine ComputedVars that need to be recalculated based on the given vars.

        Args:
            from_vars: find ComputedVar that depend on this set of vars. If unspecified, will use the dirty_vars.

        Returns:
            Set of computed vars to include in the delta.
        """
        return set(
            cvar
            for dirty_var in from_vars or self.dirty_vars
            for cvar in self.computed_var_dependencies[dirty_var]
        )

    def get_delta(self) -> Delta:
        """Get the delta for the state.

        Returns:
            The delta for the state.
        """
        delta = {}

        # Apply dirty variables down into substates
        self.dirty_vars.update(self._always_dirty_computed_vars())
        self._mark_dirty()

        # Return the dirty vars for this instance, any cached/dependent computed vars,
        # and always dirty computed vars (cache=False)
        delta_vars = (
            self.dirty_vars.intersection(self.base_vars)
            .union(self._dirty_computed_vars())
            .union(self._always_dirty_computed_vars())
        )

        subdelta = {
            prop: getattr(self, prop)
            for prop in delta_vars
            if not types.is_backend_variable(prop)
        }
        if len(subdelta) > 0:
            delta[self.get_full_name()] = subdelta

        # Recursively find the substate deltas.
        substates = self.substates
        for substate in self.dirty_substates:
            delta.update(substates[substate].get_delta())

        # Format the delta.
        delta = format.format_state(delta)

        # Return the delta.
        return delta

    def _mark_dirty(self):
        """Mark the substate and all parent states as dirty."""
        state_name = self.get_name()
        if (
            self.parent_state is not None
            and state_name not in self.parent_state.dirty_substates
        ):
            self.parent_state.dirty_substates.add(self.get_name())
            self.parent_state._mark_dirty()

        # have to mark computed vars dirty to allow access to newly computed
        # values within the same ComputedVar function
        self._mark_dirty_computed_vars()

        # Propagate dirty var / computed var status into substates
        substates = self.substates
        for var in self.dirty_vars:
            for substate_name in self.substate_var_dependencies[var]:
                self.dirty_substates.add(substate_name)
                substate = substates[substate_name]
                substate.dirty_vars.add(var)
                substate._mark_dirty()

    def _clean(self):
        """Reset the dirty vars."""
        # Recursively clean the substates.
        for substate in self.dirty_substates:
            self.substates[substate]._clean()

        # Clean this state.
        self.dirty_vars = set()
        self.dirty_substates = set()

    def dict(self, include_computed: bool = True, **kwargs) -> dict[str, Any]:
        """Convert the object to a dictionary.

        Args:
            include_computed: Whether to include computed vars.
            **kwargs: Kwargs to pass to the pydantic dict method.

        Returns:
            The object as a dictionary.
        """
        if include_computed:
            # Apply dirty variables down into substates to allow never-cached ComputedVar to
            # trigger recalculation of dependent vars
            self.dirty_vars.update(self._always_dirty_computed_vars())
            self._mark_dirty()

        base_vars = {
            prop_name: self.get_value(getattr(self, prop_name))
            for prop_name in self.base_vars
        }
        computed_vars = (
            {
                # Include the computed vars.
                prop_name: self.get_value(getattr(self, prop_name))
                for prop_name in self.computed_vars
            }
            if include_computed
            else {}
        )
        substate_vars = {
            k: v.dict(include_computed=include_computed, **kwargs)
            for k, v in self.substates.items()
        }
        variables = {**base_vars, **computed_vars, **substate_vars}
        return {k: variables[k] for k in sorted(variables)}


class DefaultState(State):
    """The default empty state."""

    pass


class StateUpdate(Base):
    """A state update sent to the frontend."""

    # The state delta.
    delta: Delta = {}

    # Events to be added to the event queue.
    events: List[Event] = []

    # Whether this is the final state update for the event.
    final: bool = True


class StateManager(Base):
    """A class to manage many client states."""

    # The state class to use.
    state: Type[State] = DefaultState

    # The mapping of client ids to states.
    states: Dict[str, State] = {}

    # The token expiration time (s).
    token_expiration: int = constants.TOKEN_EXPIRATION

    # The redis client to use.
    redis: Optional[Redis] = None

    def setup(self, state: Type[State]):
        """Set up the state manager.

        Args:
            state: The state class to use.
        """
        self.state = state
        self.redis = prerequisites.get_redis()

    def get_state(self, token: str) -> State:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        if self.redis is not None:
            redis_state = self.redis.get(token)
            if redis_state is None:
                self.set_state(token, self.state())
                return self.get_state(token)
            return cloudpickle.loads(redis_state)

        if token not in self.states:
            self.states[token] = self.state()
        return self.states[token]

    def set_state(self, token: str, state: State):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
        """
        if self.redis is None:
            return
        self.redis.set(token, cloudpickle.dumps(state), ex=self.token_expiration)


class ClientStorageBase:
    """Base class for client-side storage."""

    def options(self) -> dict[str, Any]:
        """Get the options for the storage.

        Returns:
            All set options for the storage (not None).
        """
        return {
            format.to_camel_case(k): v for k, v in vars(self).items() if v is not None
        }


class Cookie(ClientStorageBase, str):
    """Represents a state Var that is stored as a cookie in the browser."""

    name: str | None
    path: str
    max_age: int | None
    domain: str | None
    secure: bool | None
    same_site: str

    def __new__(
        cls,
        object: Any = "",
        encoding: str | None = None,
        errors: str | None = None,
        /,
        name: str | None = None,
        path: str = "/",
        max_age: int | None = None,
        domain: str | None = None,
        secure: bool | None = None,
        same_site: str = "lax",
    ):
        """Create a client-side Cookie (str).

        Args:
            object: The initial object.
            encoding: The encoding to use.
            errors: The error handling scheme to use.
            name: The name of the cookie on the client side.
            path: Cookie path. Use / as the path if the cookie should be accessible on all pages.
            max_age: Relative max age of the cookie in seconds from when the client receives it.
            domain: Domain for the cookie (sub.domain.com or .allsubdomains.com).
            secure: Is the cookie only accessible through HTTPS?
            same_site: Whether the cookie is sent with third party requests.
                One of (true|false|none|lax|strict)

        Returns:
            The client-side Cookie object.

        Note: expires (absolute Date) is not supported at this time.
        """
        if encoding or errors:
            inst = super().__new__(cls, object, encoding or "utf-8", errors or "strict")
        else:
            inst = super().__new__(cls, object)
        inst.name = name
        inst.path = path
        inst.max_age = max_age
        inst.domain = domain
        inst.secure = secure
        inst.same_site = same_site
        return inst


class LocalStorage(ClientStorageBase, str):
    """Represents a state Var that is stored in localStorage in the browser."""

    name: str | None

    def __new__(
        cls,
        object: Any = "",
        encoding: str | None = None,
        errors: str | None = None,
        /,
        name: str | None = None,
    ) -> "LocalStorage":
        """Create a client-side localStorage (str).

        Args:
            object: The initial object.
            encoding: The encoding to use.
            errors: The error handling scheme to use.
            name: The name of the storage key on the client side.

        Returns:
            The client-side localStorage object.
        """
        if encoding or errors:
            inst = super().__new__(cls, object, encoding or "utf-8", errors or "strict")
        else:
            inst = super().__new__(cls, object)
        inst.name = name
        return inst


class MutableProxy(wrapt.ObjectProxy):
    """A proxy for a mutable object that tracks changes."""

    __magic_attrs__ = set(
        [
            "add",
            "append",
            "clear",
            "difference_update",
            "discard",
            "extend",
            "insert",
            "intersection_update",
            "pop",
            "popitem",
            "remove",
            "reverse",
            "setdefault",
            "sort",
            "symmetric_difference_update",
            "update",
        ]
    )

    __mutable_types__ = (list, dict, set)

    def __init__(self, wrapped: Any, state: State, field_name: str):
        """Create a proxy for a mutable object that tracks changes.

        Args:
            wrapped: The object to proxy.
            state: The state to mark dirty when the object is changed.
            field_name: The name of the field on the state associated with the
                wrapped object.
        """
        super().__init__(wrapped)
        self._self_state = state
        self._self_field_name = field_name

    def _mark_dirty(self, wrapped=None, instance=None, args=tuple(), kwargs=None):
        """Mark the state as dirty, then call a wrapped function.

        Intended for use with `FunctionWrapper` from the `wrapt` library.

        Args:
            wrapped: The wrapped function.
            instance: The instance of the wrapped function.
            args: The args for the wrapped function.
            kwargs: The kwargs for the wrapped function.
        """
        self._self_state.dirty_vars.add(self._self_field_name)
        self._self_state._mark_dirty()
        if wrapped is not None:
            print(
                f"{wrapped.__name__} marked {self._self_field_name} as dirty on {self._self_state.get_name()}"
            )
            wrapped(*args, **(kwargs or {}))

    def __getattribute__(self, __name: str) -> Any:
        """Get the attribute on the proxied object and return a proxy if mutable.

        Args:
            __name: The name of the attribute.

        Returns:
            The attribute value.
        """
        v = super().__getattribute__(__name)
        if callable(v) and __name in super().__getattribute__("__magic_attrs__"):
            return wrapt.FunctionWrapper(
                v,
                super().__getattribute__("_mark_dirty"),
            )
        if (
            isinstance(v, super().__getattribute__("__mutable_types__"))
            and __name != "__wrapped__"
        ):
            return MutableProxy(v, self._self_state, self._self_field_name)
        return v

    def __getitem__(self, key) -> Any:
        """Get the item on the proxied object and return a proxy if mutable.

        Args:
            key: The key of the item.

        Returns:
            The item value.
        """
        v = super().__getitem__(key)
        if isinstance(v, self.__mutable_types__):
            return MutableProxy(v, self._self_state, self._self_field_name)
        return v

    def __delattr__(self, name):
        """Delete the attribute on the proxied object and mark state dirty.

        Args:
            name: The name of the attribute.
        """
        self._mark_dirty(super().__delattr__, args=(name,))

    def __delitem__(self, key):
        """Delete the item on the proxied object and mark state dirty.

        Args:
            key: The key of the item.
        """
        self._mark_dirty(super().__delitem__, args=(key,))

    def __setitem__(self, key, value):
        """Set the item on the proxied object and mark state dirty.

        Args:
            key: The key of the item.
            value: The value of the item.
        """
        self._mark_dirty(super().__setitem__, args=(key, value))

    def __setattr__(self, name, value):
        """Set the attribute on the proxied object and mark state dirty.

        If the attribute starts with "_self_", then the state is NOT marked
        dirty as these are internal proxy attributes.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.
        """
        if name.startswith("_self_"):
            super().__setattr__(name, value)
            return
        self._mark_dirty(super().__setattr__, args=(name, value))
