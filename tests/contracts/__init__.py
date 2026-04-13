"""Port contract test base classes.

Each mixin defines the behavioural contract every implementation of a
given port must obey. Concrete test modules subclass the mixin and
override `_build_*()` to return their particular adapter. The shared
tests then run against every implementation uniformly.
"""
