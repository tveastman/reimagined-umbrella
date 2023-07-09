#!/usr/bin/env python3

"""
Twitter's APIv2 and Oauth2 authentication flow.

Using httpx's synchronous client for the first cut.

Does the authorizatino flow and gets you a token.

I got this far basically to confirm that the free API plan is
useless for my purposes. And the $100 dollar per month plan's
rate limits also make it completely unusable for Secateur.

"""

import logging
import webbrowser
import os
import secrets
import http.server
from typing import Final
import dataclasses

import structlog
import keyring
from authlib.integrations.httpx_client import OAuth2Client
from rich import print

logging.basicConfig(level=logging.DEBUG)
logger = structlog.getLogger()

client_id: str = keyring.get_password("twitter_oauth2", "client_id")
client_secret: str = keyring.get_password("twitter_oauth2", "client_secret")

@dataclasses.dataclass(frozen=True)
class AuthorizationRequestState:
    state: str
    code_verifier: str


def listen(port: int = 8000) -> str:
    """Create a server, listen for a single http request and return the request path.

    Shut down the server after it receives a single web request.
    """

    class Handler(http.server.BaseHTTPRequestHandler):
        last_requested_path = ""

        def do_GET(self):
            self.wfile.write(b"You can close this browser window now.\n\n")
            self.wfile.write(self.path.encode())
            self.send_response(200)
            Handler.last_requested_path = self.path

    server_address = ("127.0.0.1", port)
    with http.server.HTTPServer(
        server_address=server_address,
        RequestHandlerClass=Handler,
    ) as httpd:
        httpd.handle_request()
        last_requested_path = Handler.last_requested_path
    return last_requested_path


def open_authorization_in_browser() -> AuthorizationRequestState:
    """Open a browser and request authorization from Twitter

    Returns the state required to handle the authentication response.
    """
    authorization_endpoint: Final = "https://twitter.com/i/oauth2/authorize"

    scope = [
        "block.read",
        "block.write",
        "follows.read",
        "offline.access",
        "users.read",
        "tweet.read",
        "tweet.write"
    ]
    code_verifier = secrets.token_urlsafe(10)
    auth_req_client = OAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
        code_challenge_method="S256",
        redirect_uri="http://localhost:8000/complete/twitter2/",
    )
    uri, state = auth_req_client.create_authorization_url(
        authorization_endpoint, code_verifier=code_verifier
    )
    ars = AuthorizationRequestState(state=state, code_verifier=code_verifier)
    logger.info("authorization request state", ars=ars)
    webbrowser.open(uri)
    return ars


def fetch_authorization_token(
    authorization_request_state: AuthorizationRequestState, authorization_response: str
) -> dict:
    token_endpoint: Final = "https://api.twitter.com/2/oauth2/token"
    # Fetch the token using a new client.
    fetch_token_client = OAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
        code_challenge_method="S256",
        redirect_uri="http://localhost:8000/complete/twitter2/",
        # it works without this argument but misses a security check
        # pretty dumb to silently do the less secure thing
        state=authorization_request_state.state,
    )
    token = fetch_token_client.fetch_token(
        token_endpoint,
        authorization_response=authorization_response,
        code_verifier=authorization_request_state.code_verifier,
        client_id=client_id,
    )
    logger.info("fetch_token()", **token)
    return token

def get_blocks(token: dict):
    client = OAuth2Client(token=token)
    user_id = "69190199"
    blocks_url = f"https://api.twitter.com/2/users/{user_id}/blocking"
    response = client.get(blocks_url, params={
        "user.fields": "created_at"
    })
    print(response.json())



def get_user_info(token: dict):
    client = OAuth2Client(
        token=token,
    )
    me_url = "https://api.twitter.com/2/users/me"
    fields = "created_at,description"
    params = {"user.fields": fields}
    response = client.get(me_url, params=params)
    print(response.json())

def tweet(token, content):
    url = "https://api.twitter.com/2/tweets"
    client = OAuth2Client(token=token)
    response = client.post(url, json=dict(
        text="asdf"
    ))
    print(response.json())


def main():
    ars = open_authorization_in_browser()
    authorization_response = listen()
    token = fetch_authorization_token(ars, authorization_response)
    get_user_info(token)
    #get_blocks(token)
    tweet(token, "asdf")


if __name__ == "__main__":
    main()
