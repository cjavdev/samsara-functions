from samsara.function import Function


def handler(event, _):
    print("Running the scratch handler...")
    print("Event:")
    print(event)
    print("--------------------------------")

    function = Function()
    secrets = function.secrets().load()
    print("Secrets:")
    print(secrets)
    print("--------------------------------")


if __name__ == "__main__":
    handler(None, None)