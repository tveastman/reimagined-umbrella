"""
A version of function "memoization" where the caller "owns" the cache

Sometimes you want to cache a series of function calls but only throughout
the scope of a single operation larger operation. You don't want the cache
to last beyond that, and you don't want the cached calls spilling into
other operations.

The decorator in this library works like functools.cache but the caller passes
in the `cache` object and therefore controls its usage and its lifecycle.

An example use-case is a complex operation that is making a lot of redundant
database lookups, and you want to cache those lookups but keep that cache
scoped only to the operation and not leak to other uses of the function.

I need help naming the bits of this code! Please help me come up with intuitive
names for:

 - the module as a whole
 - the cache object class
 - the function decorator
 - the keyword argument that is used to pass the cache object

Usage:

>>> def parent_function():
>>>     cache = ScopeCache()
>>>     for i in range(50):
>>>         slow_function(scope_cache=cache)
>>>     # when `parent_function` ends the cache is garbage collected
>>>
>>> @memoize_with_scope_cache
>>> def slow_function(*args, scope_cache: ScopeCache | None = None, **kwargs):
>>>     ...

"""


import functools
import collections
from typing import Final, Callable, Any
import logging

logger = logging.getLogger(__name__)

KWARG_NAME: Final = "scope_cache"

ScopeCacheType = collections.UserDict[Callable, functools._lru_cache_wrapper]


class ScopeCache(ScopeCacheType):
    """Cache object used by functions decorated with @memoize_with_scope_cache

    When passed to a function decorated with @memoize_with_scope_cache, the
    function

    Internally, this is a dictionary mapping the original function to the
    lru_cache decorated version of the function.
    """
    def cache_info(self) -> dict:
        return {key: value.cache_info() for key, value in self.data.items()}

    def cache_clear(self) -> None:
        for value in self.data.values():
            value.cache_clear()


def memoize_with_scope_cache(user_function: Callable) -> Callable:
    """
    Selectively memoize the function using a ScopeCache

    If a ScopeCache instance is passed in with the `scope_cache=`
    keyword argument, then the function call is memoized and the
    result cached in the ScopeCache instance.

    Subsequent calls with the same ScopeCache *and* arguments will
    return the cached result.

    NOTE: because the `scope_cache=` keyword argument is removed
    from the function call, recursive calls to other
    memoized functions will not have the cache passed to them.
    """
    @functools.wraps(user_function)
    def wrapper(*args, **kwargs) -> Any:
        scope_cache = kwargs.pop(KWARG_NAME, None)
        cache_decorator: Final = functools.cache

        if scope_cache is None:
            # If no cache is provided we just use the vanilla function
            logger.debug("calling the original `user_function`")
            return user_function(*args, **kwargs)

        # Fetch (maybe create) the memoized function from the scope cache
        if (memoized_user_function := scope_cache.get(user_function)) is None:
            memoized_user_function = scope_cache[user_function] = (
                cache_decorator(user_function)
            )
            logger.debug("created %s from %s", memoized_user_function, user_function)

        # call the memoized function
        logger.debug("calling the memoized function %s", memoized_user_function)
        return memoized_user_function(*args, **kwargs)

    return wrapper
