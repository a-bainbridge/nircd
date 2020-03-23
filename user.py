import time
from util import HOSTNAME


class User(object):
    sock = None
    connection_info = ()
    nickname = ''
    username = "*"
    realname = ''
    channels = []
    last_pong = 0
    mode_away = False
    initialized = False

    def __init__(self, **kwargs):
        self.hostname = None
        self.last_pong = time.time()
        self.channels = []
        self.mode_away = False
        self.initialized = False
        self.realname = ''
        for arg, val in kwargs.items():
            setattr(self, arg, val)

    def send_data_add_newlines_for_me(self, data: str):
        # noinspection PyTupleAssignmentBalance
        conn, addr = self.connection_info
        print("s:", data)
        conn.send(bytes(data + '\r\n', encoding="UTF-8"))

    def send_structured_data(self, hostname, cmd, target, contents):
        self.send_data_add_newlines_for_me(":" + hostname + " " + cmd + " " + target + " :" + contents)

    def send_raw(self, contents):
        self.send_data_add_newlines_for_me(contents)

    def send_reply(self, number, message):
        self.send_structured_data(HOSTNAME, number, self.nickname, message)

    def send_ping(self):
        self.send_data_add_newlines_for_me("PING :" + HOSTNAME)

    def send_who(self, channel):
        strbuf = ""
        for uzer in channel.channel_users:
            strbuf = strbuf + ":" + HOSTNAME + " " + "352" + " " + self.nickname + " " + channel.name + " " \
                     + uzer.username + " " + str(
                uzer.get_hostname()) + " " + HOSTNAME + " " + uzer.nickname \
                     + " " + "H@" + " :0 realname" + "\r\n"
        strbuf = strbuf + ":" + HOSTNAME + " " + "315 " + self.nickname + " " + channel.name + " :End of /WHO list"
        self.send_raw(strbuf)

    def update_nick(self, nick):
        if not self.nickname == "":
            for chan in self.channels:
                chan.send_nick(self, nick)
            self.send_data_add_newlines_for_me(":" + self.nickname + " NICK " + nick)
        self.nickname = nick

    def get_proper_name(self):
        return self.nickname + "!" + self.username + "@" + self.get_hostname()

    def append_channel(self, chan):
        self.channels.append(chan)

    def get_hostname(self):
        return self.hostname[0]
