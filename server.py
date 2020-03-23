import socketserver, socket
import selectors
import types
import time
import configparser
import sys
from typing import List, Optional

from user import User
from channel import Channel

from util import HOSTNAME, validate_nickname

import lua_util

sel = selectors.DefaultSelector()


def get_command_name(cmd: str) -> str:
    return cmd.split(' ')[0]


def spliterate_command_params(cmd: str) -> list:
    return cmd.split(" ")


def spliterate(raw_cmds: str) -> list:
    return raw_cmds.strip('\r').splitlines()


class Server(object):
    users = []
    channels = []
    last_global_ping = 0
    ping_timeout = 0.0
    ping_interval = 0.0
    lua_func = None
    lua_inst = None

    def __init__(self):
        self.last_global_ping = time.time()
        self.motd = ""
        self.read_config()
        self.lua_func = None
        self.lua_inst = None

    def read_config(self):
        parser = configparser.ConfigParser()
        parser.read("server-configuration.ini")
        general_settings = parser["Server"]
        self.ping_timeout = float(general_settings["ping-timeout"])
        self.ping_interval = float(general_settings["ping-interval"])
        self.motd = parser["MOTD"]["motd"]
        print("MOTD:")
        print(self.motd)
        for k, v in parser.items("ChannelList"):
            if v == "True":
                channel = Channel()
                channel.name = "#" + k
                channel.topic = parser[k]["topic"]
                self.channels.append(channel)
                print("Created channel", channel.name)

    def tick_pings(self):
        if time.time() - self.last_global_ping > self.ping_interval:
            self.last_global_ping = time.time()
            for user in self.users:
                try:
                    user.send_ping()
                except:
                    for channel_cond in user.channels:
                        channel_cond.disconnect_quit(user, "Connection lost - Unknown error")
                        if user in self.users:
                            self.users.remove(user)
                        sel.unregister(user.connection_info[0])
                        user.connection_info[0].close()
        for user in self.users:
            if time.time() - user.last_pong > self.ping_timeout:
                for channel_cond in user.channels:
                    channel_cond.disconnect_quit(user, "Connection lost - Did not respond")
                    if user in self.users:
                        self.users.remove(user)
                    try:
                        sel.unregister(user.connection_info[0])
                        user.connection_info[0].close()
                    except Exception as e:
                        print(e)

    def find_user(self, address_pair: tuple) -> Optional[User]:
        for user in self.users:
            if user.connection_info[1] == address_pair:
                return user
        return None

    def find_user_by_name(self, name: str) -> Optional[User]:
        for user in self.users:
            if user.nickname == name:
                return user
        return None

    def find_channel(self, name: str) -> Optional[Channel]:
        for channel in self.channels:
            if channel.name == name:
                return channel
        return None

    def get_motd(self):
        return self.motd

    def process_cmds_for_user(self, commands: List[str], user: User):
        for cmd in commands:
            name = get_command_name(cmd)
            if name == "QUIT":
                for channel_cond in user.channels:
                    reason = cmd.split(":")
                    if len(reason) > 1:
                        reason = reason[1]
                    else:
                        reason = "No reason specified"
                    channel_cond.disconnect_quit(user, reason)
                self.users.remove(user)
                sel.unregister(user.connection_info[0])
                user.connection_info[0].close()
            elif name == "WHO":
                channel = self.find_channel(cmd.split(" ")[1])
                if channel is None:
                    continue
                if user is not None:
                    user.send_who(channel)
            elif name == "LIST":
                buf = ""
                user.send_data_add_newlines_for_me(
                    ":" + HOSTNAME + " 321 " + user.nickname + " Channel :Users  Name")
                for channel in self.channels:
                    buf = buf + ":" + HOSTNAME + " 322 " + user.nickname + " " + channel.name + " " + str(
                        len(channel.channel_users) + 1337) + " :" + channel.topic + "\r\n"
                buf = buf + ":" + HOSTNAME + " 323 :End of LIST"
                user.send_data_add_newlines_for_me(buf)
            elif name == "PART":
                chan_name = cmd.split(" ")[1]
                reason = cmd.split(":")
                if len(reason) == 1:
                    reason = "Unspecified reason"
                else:
                    reason = cmd.replace(reason[0] + ":", "", 1)
                channels = []
                for channel_name in chan_name.split(","):
                    channels.append(self.find_channel(channel_name))
                for chan in channels:
                    if chan is not None:
                        chan.disconnect_part(user, reason)

    def accept(self, sock_file: socket.socket):
        connection, address = sock_file.accept()
        connection.setblocking(False)
        data = types.SimpleNamespace(address=address, in_data=b'', out_data=b'')
        event = selectors.EVENT_READ | selectors.EVENT_WRITE
        sel.register(connection, event, data=data)
        connection.send(bytes("NOTICE AUTH :*** Processing connection to " + HOSTNAME + "\r\n", encoding="UTF-8"))
        connection.send(bytes("NOTICE AUTH :*** Looking up your hostname...\r\n", encoding="UTF-8"))
        try:
            hname = socket.gethostbyaddr(address[0])
            print(hname)
            user = User(connection_info=(connection, address), hostname=hname)
            connection.send(bytes("NOTICE AUTH :*** Found your hostname\r\n", encoding="UTF-8"))
        except Exception:
            connection.send(
                bytes("NOTICE AUTH :*** Couldn't find your hostname. Reverting to naive.\r\n", encoding="UTF-8"))
            user = User(connection_info=(connection, address), hostname=address)
        self.users.append(user)

    def handle(self, key, mask):
        global recv_data
        sock = key.fileobj
        data = key.data

        if mask & selectors.EVENT_READ:
            try:
                recv_data = sock.recv(1024)
            except Exception as e:
                print('closing connection to', data.address)
                maybe_user = self.find_user(data.address)
                if maybe_user is not None:
                    if maybe_user in self.users:
                        self.users.remove(maybe_user)
                    for chan in maybe_user.channels:
                        if maybe_user in chan.channel_users:
                            chan.disconnect_quit(maybe_user, "Lost connection")
                sel.unregister(sock)
                sock.close()
            if recv_data:
                message = str(recv_data.decode('UTF-8'))
                print('received', repr(message), 'from', data.address)
                maybe_user = self.find_user(data.address)
                lua_user = maybe_user
                lua_util.create_real_globals(self.lua_inst, self, lua_user)
                lua_util.lua_handle(self.lua_func, message)
                self.process_cmds_for_user(spliterate(message), maybe_user)
        if mask & selectors.EVENT_WRITE:
            if data.out_data:
                sent = sock.send(data.out_data)
                data.out_data = data.out_data[sent:]


if __name__ == "__main__":
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.bind(("0.0.0.0", 31337))
    listen_sock.listen()
    listen_sock.setblocking(False)
    sel.register(listen_sock, selectors.EVENT_READ, data=None)
    server = Server()
    server.lua_func, server.lua_inst = lua_util.load_lua()
    while True:
        # event loop
        events = sel.select(timeout=1)
        try:
            for key, mask in events:
                if key.data is None:
                    server.accept(key.fileobj)
                else:
                    server.handle(key, mask)
        except Exception as e:
            print(e)
        server.tick_pings()
        if lua_util.should_reload_lua():
            print("Reloading lua!")
            try:
                server.lua_func, server.lua_inst = lua_util.load_lua()
            except Exception as e:
                print(e)
