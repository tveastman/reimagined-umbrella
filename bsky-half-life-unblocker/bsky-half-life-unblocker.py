import rich.console
import asyncio
import pydantic
import pathlib
import time
import random
import atproto
import contextlib

STATE_FILENAME = pathlib.Path.home() / ".bsky-half-life-unblocker-state.json"

console = rich.console.Console()

HALF_LIFE = 365.25 / 3.0
THRESHOLD = 0.01


def daystamp():
    """The unix timestamp but in 'days' instead of seconds."""
    return time.time() / (60 * 60 * 24)


class State(pydantic.BaseModel):
    """Need to keep some state but don't need a database"""

    session: str | None = None
    last_unblock_run_daystamp: float = pydantic.Field(default_factory=daystamp)
    app_bsky_graph_block_list: dict[str, atproto.models.AppBskyGraphBlock.Record] = (
        pydantic.Field(default_factory=dict)
    )

    @classmethod
    def load(cls):
        try:
            text = pathlib.Path(STATE_FILENAME).read_text()
            return cls.model_validate_json(text)
        except FileNotFoundError:
            return cls()

    def save(self):
        start = time.time()
        pathlib.Path(STATE_FILENAME).write_text(self.model_dump_json(indent=1))
        duration = time.time() - start
        console.log(f"saved state in {duration} seconds")

    @classmethod
    @contextlib.contextmanager
    def auto_load_and_save(cls):
        state = cls.load()
        yield state
        state.save()


def keep_session_updated(client, state):
    """Update the state file whenever the session token is refreshed"""

    async def on_session_change(event, session):
        state.session = session.export()

    client.on_session_change(on_session_change)


async def update_block_list(client, block_list):
    cursor = None
    overlap = False
    new_records = 0
    while True:
        console.log(f"fetching page of block records using cursor {cursor!r}")
        lrr = await client.app.bsky.graph.block.list(
            repo=client.me.did, cursor=cursor, limit=100
        )
        for uri, record in lrr.records.items():
            if uri in block_list:
                overlap = True
            else:
                new_records += 1
            block_list[uri] = record
        cursor = lrr.cursor
        if cursor is None:
            console.log("last page fetched")
            break
        if overlap:
            console.log("fetched all new records")
            break
    console.log(f"new block records: {new_records}")


async def unblock(client, block_list, uri):
    record = block_list[uri]
    rkey = atproto.AtUri.from_str(uri).rkey
    link = f"https://bsky.app/profile/{record.subject}"
    result = await client.app.bsky.graph.block.delete(repo=client.me.did, rkey=rkey)
    if result:
        del block_list[uri]
        console.print(f"unblocked [link={link}]{record.subject}[/link]")
    else:
        console.print(f"failed to unblock [link={link}]{record.subject}[/link]")


async def randomly_unblock(client, block_list, probability):
    all_items = list(block_list.items())
    num = random.binomialvariate(len(all_items), probability)
    console.log(f"unblocking {num} out of {len(all_items)}")
    chosen_items = random.sample(all_items, num)

    async with asyncio.TaskGroup() as task_group:
        for uri, record in chosen_items:
            task_group.create_task(
                unblock(client, block_list, uri), name=f"unblock {uri}"
            )


def calculate_decay_probability(time, half_life):
    """Return the probability for each item to be deleted."""
    remaining = 2.0 ** (-time / half_life)
    probability = 1.0 - remaining
    return probability


async def main():
    with State.auto_load_and_save() as state:
        current_daystamp = daystamp()
        time_period = current_daystamp - state.last_unblock_run_daystamp
        probability = calculate_decay_probability(time_period, HALF_LIFE)
        console.log("Days since last run:", time_period)
        console.log(f"Probability of unblocking per account: {probability:%}")

        threshold = THRESHOLD
        if probability < threshold:
            console.log(f"Waiting till the probability is greater than {threshold:%}")
            return

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

        await update_block_list(client, state.app_bsky_graph_block_list)
        state.last_unblock_run_daystamp = current_daystamp
        await randomly_unblock(client, state.app_bsky_graph_block_list, probability)

        console.log(f"number of block records: {len(state.app_bsky_graph_block_list)}")


asyncio.run(main(), debug=False)
