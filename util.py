valid_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

HOSTNAME = "irc.bebop.rodeo"


def validate_nickname(nick: str) -> bool:
    if len(nick) > 9 or len(nick) == 0:
        return False
    if nick.strip(valid_chars) != "":
        return False
    return True
