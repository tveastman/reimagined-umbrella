import itertools
import keyring
import rich.console
import asyncio
import pydantic
import pathlib
import time
import random
import atproto
import contextlib
import gzip
import sys
import typer
from rich.markup import escape

STATE_FILENAME = pathlib.Path.home() / ".bsky-half-life-unblocker-state.json.gz"

console = rich.console.Console()
app = typer.Typer()

HALF_LIFE = 365.25 / 3.0
THRESHOLD = 0.002


def daystamp():
    """The unix timestamp but in 'days' instead of seconds."""
    return time.time() / (60 * 60 * 24)


class State(pydantic.BaseModel):
    """Need to keep some state but don't need a database"""

    session: str = ""
    last_unblock_run_daystamp: float = pydantic.Field(default_factory=daystamp)
    # rkey: did
    app_bsky_graph_block_list: dict[str, str] = pydantic.Field(default_factory=dict)
    block_queue: set[str] = pydantic.Field(default_factory=set)

    @classmethod
    def load(cls):
        try:
            text = gzip.decompress(pathlib.Path(STATE_FILENAME).read_bytes()).decode(
                "utf-8"
            )
            return cls.model_validate_json(text)
        except FileNotFoundError:
            return cls()

    def save(self):
        start = time.time()
        pathlib.Path(STATE_FILENAME).write_bytes(
            gzip.compress(self.model_dump_json(indent=1).encode("utf-8"))
        )
        duration = time.time() - start
        console.log(f"saved state in {duration} seconds")

    @classmethod
    @contextlib.contextmanager
    def auto_load_and_save(cls):
        state = cls.load()
        try:
            yield state
        finally:
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
            at_uri = atproto.AtUri.from_str(uri)
            if at_uri.rkey in block_list:
                overlap = True
            else:
                new_records += 1
            block_list[at_uri.rkey] = record.subject
        cursor = lrr.cursor
        if cursor is None:
            console.log("last page fetched")
            break
        if overlap:
            console.log("fetched all new records")
            break
    console.log(f"new block records: {new_records}")


async def unblock_rkey(client, block_list, rkey):
    did = block_list[rkey]
    link = f"https://bsky.app/profile/{did}"
    result = await client.app.bsky.graph.block.delete(repo=client.me.did, rkey=rkey)
    if result:
        del block_list[rkey]
        console.print(f"unblocked [link={link}]{did}[/link]")
    else:
        console.print(f"failed to unblock [link={link}]{did}[/link]")


async def randomly_unblock(client, block_list, probability):
    all_items = list(block_list.items())
    num = random.binomialvariate(len(all_items), probability)
    console.log(f"unblocking {num} out of {len(all_items)}")
    chosen_items = random.sample(all_items, num)

    async with asyncio.TaskGroup() as task_group:
        for uri, record in chosen_items:
            task_group.create_task(
                unblock_rkey(client, block_list, uri), name=f"unblock {uri}"
            )


def calculate_decay_probability(time, half_life):
    """Return the probability for each item to be deleted."""
    remaining = 2.0 ** (-time / half_life)
    probability = 1.0 - remaining
    return probability


async def get_client(state: State) -> atproto.AsyncClient:
    client = atproto.AsyncClient()
    keep_session_updated(client, state)

    if state.session:
        console.log("logging in using exported session string")
        await client.login(session_string=state.session)
    else:
        console.log("logging in using application password")
        username = input("Username: ")
        password = keyring.get_password("bluesky", username)
        await client.login(username, password)
    return client


async def half_life_unblocker_main(state: State):
    current_daystamp = daystamp()
    time_period = current_daystamp - state.last_unblock_run_daystamp
    probability = calculate_decay_probability(time_period, HALF_LIFE)
    console.log("Days since last run:", time_period)
    console.log(f"Probability of unblocking per account: {probability:%}")

    threshold = THRESHOLD
    if probability < threshold:
        console.log(f"Waiting till the probability is greater than {threshold:%}")
        return

    client = await get_client(state)
    await update_block_list(client, state.app_bsky_graph_block_list)

    state.last_unblock_run_daystamp = current_daystamp
    await randomly_unblock(client, state.app_bsky_graph_block_list, probability)

    console.log(f"number of block records: {len(state.app_bsky_graph_block_list)}")


async def iterate_over_all_followers(client, did):
    cursor = None
    while True:
        console.log(f"fetching page of followers using cursor {cursor!r}")
        response = await client.app.bsky.graph.get_followers(
            params=atproto.models.app.bsky.graph.get_followers.Params(
                actor=did,
                cursor=cursor,
                limit=100,
            )
        )
        for follower in response.followers:
            yield follower
        cursor = response.cursor
        if cursor is None:
            break


async def add_followers_to_block_queue(state: State, handle: str):
    client = await get_client(state)
    resolver = atproto.AsyncIdResolver()
    did = await resolver.handle.resolve(handle)
    assert did != client.me.did, "Don't try to block yourself"
    console.log("did", did, highlight=False)
    async for follower in iterate_over_all_followers(client, did):
        state.block_queue.add(follower.did)
    console.log(f"{len(state.block_queue)=}")


# async def run_block_queue(state: State):
#     client = await get_client(state)
#     while state.block_queue:
#         did = state.block_queue.pop()
#         state.block_queue.add(did)
#         response = await client.app.bsky.graph.block.create(
#             repo=client.me.did,
#             record=atproto.models.app.bsky.graph.block.Record(
#                 created_at=client.get_current_time_iso(), subject=did
#             ),
#         )
#         at_uri = atproto.AtUri.from_str(response.uri)
#         state.app_bsky_graph_block_list[at_uri.rkey] = did
#         state.block_queue.remove(did)
#         console.log(f"Blocked {did}", highlight=False)
#

async def run_block_queue_batched(state: State):
    batch_size = 200
    count = 0
    client = await get_client(state)
    all_currently_blocked_dids = set(state.app_bsky_graph_block_list.values())
    state.block_queue -= all_currently_blocked_dids
    block_queue_list = list(state.block_queue)
    for batch in itertools.batched(block_queue_list, batch_size):
        writes = []
        for did in batch:
            create = atproto.models.com.atproto.repo.apply_writes.Create(
                collection="app.bsky.graph.block",
                value=atproto.models.app.bsky.graph.block.Record(
                    created_at=client.get_current_time_iso(),
                    subject=did,
                ),
            )
            writes.append(create)
        response = await client.com.atproto.repo.apply_writes(
            data=atproto.models.com.atproto.repo.apply_writes.Data(
                repo=client.me.did, writes=writes
            )
        )
        for r, result in enumerate(response.results):
            print(result.validation_status)
            did = batch[r]
            at_uri = atproto.AtUri.from_str(result.uri)
            state.app_bsky_graph_block_list[at_uri.rkey] = batch[r]
            state.block_queue.remove(did)
            link = f"https://bsky.app/profile/{did}"
            console.print(f"blocked [link={link}]{did}[/link]")
        count += batch_size
        if count >= 1_000:
            break

async def update_block_list_main(state: State):
    client = await get_client(state)
    await update_block_list(client, state.app_bsky_graph_block_list)

@app.command()
def unblock():
    with State.auto_load_and_save() as state:
        asyncio.run(half_life_unblocker_main(state))


@app.command()
def block():
    with State.auto_load_and_save() as state:
        asyncio.run(run_block_queue_batched(state))
@app.command()
def update():
    with State.auto_load_and_save() as state:
        asyncio.run(update_block_list_main(state))

@app.command()
def block_followers(handle: str):
    with State.auto_load_and_save() as state:
        asyncio.run(add_followers_to_block_queue(state, handle))



if __name__ == "__main__":
    app()
