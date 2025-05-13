import time

import requests

from resistant_kafka_avataa.common_exceptions import TokenIsNotValid


def get_token_for_kafka_by_keycloak(conf):
    payload = {
        "grant_type": "client_credentials",
        "scope": "profile",
    }

    attempt = 5
    while attempt > 0:
        try:
            response = requests.post(
                url="https://auth.avataa.dev/realms/avataa/protocol/openid-connect/token",
                timeout=30,
                auth=(
                    "kafka",
                    "jgzLadFycvGvtuxVYtPVDn7nW6k4xjDG"
                ),
                data=payload,
            )
        except ConnectionError:
            time.sleep(1)
            attempt -= 1

        else:
            if response.status_code == 200:
                token = response.json()
                return token["access_token"], time.time() + float(token["expires_in"])

            time.sleep(1)
            attempt -= 1

    raise TokenIsNotValid(
        "Token verification service unavailable"
    )
