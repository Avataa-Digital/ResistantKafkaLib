"""Example of an ``oauth_cb`` callback for KafkaSecurityConfig.

This module is an example and is not part of the published package. Copy it into
your service and adapt it.

Credentials are read from the environment and must never be written into the
source code. Required variables:

- ``KEYCLOAK_TOKEN_URL`` — token endpoint, e.g.
  ``https://<keycloak-host>/realms/<realm>/protocol/openid-connect/token``
- ``KEYCLOAK_CLIENT_ID`` — client id
- ``KEYCLOAK_CLIENT_SECRET`` — client secret

A missing variable raises ``KeyError`` naming it, so a misconfiguration fails
loudly instead of turning into a puzzling 401.
"""

import os
import time

import requests

from resistant_kafka_avataa.common_exceptions import TokenIsNotValid


def get_token_for_kafka_by_keycloak(conf):
    """
    Fetch an access token from Keycloak using the client_credentials flow.

    :param conf: The `sasl.oauthbearer.config` string passed in by librdkafka.
                 Unused here; kept because librdkafka calls the callback with it.

    :returns: Tuple of (access token, absolute expiry timestamp in seconds).

    :raises TokenIsNotValid: If the token endpoint did not answer with 200
                             within the allowed number of attempts.
    """
    token_url = os.environ["KEYCLOAK_TOKEN_URL"]
    client_id = os.environ["KEYCLOAK_CLIENT_ID"]
    client_secret = os.environ["KEYCLOAK_CLIENT_SECRET"]

    payload = {
        "grant_type": "client_credentials",
        "scope": "profile",
    }

    attempt = 5
    while attempt > 0:
        try:
            response = requests.post(
                url=token_url,
                timeout=30,
                auth=(client_id, client_secret),
                data=payload,
            )
        # RequestException is the common base of every requests error, so this
        # covers both a dead endpoint (ConnectionError) and the timeout above
        # (Timeout). Catching the builtin ConnectionError would catch neither:
        # requests raises its own class of that name, and the two are only
        # related through OSError.
        except requests.exceptions.RequestException:
            time.sleep(1)
            attempt -= 1

        else:
            if response.status_code == 200:
                token = response.json()
                return token["access_token"], time.time() + float(
                    token["expires_in"]
                )

            time.sleep(1)
            attempt -= 1

    raise TokenIsNotValid("Token verification service unavailable")
