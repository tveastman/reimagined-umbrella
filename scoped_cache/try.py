import logging
import scoped_cache
from rich import print

logging.basicConfig(level=logging.DEBUG, format="%(message)s")

@scoped_cache.memoize_with_scope_cache
def count_vowels(sentence):
    print(f"Counting vowels in {sentence!r}")
    return sum(sentence.count(vowel) for vowel in 'AEIOUaeiou')

def main():

    print(count_vowels("This call is not cached"))

    cache = scoped_cache.ScopeCache()
    print(count_vowels("This call is cached", scope_cache=cache))
    print(count_vowels("This call is cached", scope_cache=cache))
    print(count_vowels("This call is cached", scope_cache=cache))
    print(cache.cache_info())

if __name__ == "__main__":
    main()
