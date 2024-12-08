import rich.console
import atproto
import asyncio
import pydantic
import pathlib
import time
import random

STATE_FILENAME = pathlib.Path.home() / ".bsky-half-life-unblocker-state.json"

console = rich.console.Console()


def daystamp():
    """The unix timestamp but in 'days' instead of seconds."""
    return time.time() / (60 * 60 * 24)


class State(pydantic.BaseModel):
    """Need to keep some state but don't need a database"""

    session: str | None = None
    last_unblock_run_daystamp: float = pydantic.Field(default_factory=daystamp)

    @classmethod
    def load(cls):
        try:
            text = pathlib.Path(STATE_FILENAME).read_text()
            return cls.model_validate_json(text)
        except FileNotFoundError:
            return cls()

    def save(self):
        pathlib.Path(STATE_FILENAME).write_text(self.model_dump_json(indent=2))


def keep_session_updated(client, state):
    """Update the state file whenever the session token is refreshed"""

    async def on_session_change(event, session):
        console.log("saving updated session string")
        state.session = session.export()
        state.save()

    client.on_session_change(on_session_change)


async def fetch_all_block_records(client):
    records = {}
    cursor = None
    while True:
        console.log(f"fetching page of block records using cursor {cursor!r}")
        lrr = await client.app.bsky.graph.block.list(
            repo=client.me.did, cursor=cursor, limit=100
        )
        records.update(lrr.records)
        cursor = lrr.cursor
        if cursor is None:
            break
    console.log(f"fetched {len(records)} records")
    return records


def calculate_decay_probability(time, half_life):
    """Return the probability for each item to be deleted."""
    remaining = 2.0 ** (-time / half_life)
    probability = 1.0 - remaining
    return probability


async def main():
    state = State.load()
    client = atproto.AsyncClient()
    keep_session_updated(client, state)

    if state.session:
        console.log("logging in using exported session string")
        await client.login(session_string=state.session)
    else:
        console.log("logging in using application password")
        username = input("Username: ")
        password = input("app password: ")
        await client.login(username, password)

    block_records = await fetch_all_block_records(client)

    current_daystamp = daystamp()
    time_period = current_daystamp - state.last_unblock_run_daystamp
    probability = calculate_decay_probability(time_period, 180)
    console.log("Days since last run:", time_period)
    console.log(f"Probability of unblocking per account: {probability:%}")

    for uri, record in block_records.items():
        if random.random() >= probability:
            # ...stays blocked.
            continue

        # unblock this account.
        rkey = atproto.AtUri.from_str(uri).rkey
        await client.app.bsky.graph.block.delete(repo=client.me.did, rkey=rkey)
        console.log(f"unblocked: https://bsky.app/profile/{record.subject}")

    state.last_unblock_run_daystamp = current_daystamp
    state.save()


asyncio.run(main())
