from _socket import gethostname


class Server:
    @staticmethod
    def get_hostname() -> str:
        return gethostname().lower()
