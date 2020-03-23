import lupa
import fileinput
import os
from lupa import LuaRuntime
import time
from user import User
from channel import Channel
import util

fd_time_boot = 0


def dict_from_lua_tbl(luatbl):
    d = {}
    for k, v in luatbl.items():
        if str(type(v)) == "<class 'lupa._lupa._LuaTable'>":
            d[k] = dict_from_lua_tbl(v)
        else:
            d[k] = v
    return d


def lua_handle(lua_inst, str):
    a = lua_inst(str, time)
    d = dict_from_lua_tbl(a)
    print(d)


def should_reload_lua() -> bool:
    statinfo = os.stat('handle.lua')
    return statinfo.st_mtime != fd_time_boot


def load_lua():
    global fd_time_boot
    lua = LuaRuntime(unpack_returned_tuples=True)
    statinfo = os.stat('handle.lua')
    fd_time_boot = statinfo.st_mtime
    _ = lua.require('handle')
    yep = lua.eval(
        '''
        function(i, time)
            return handle_cmd(i, time)
        end
        '''
    )
    return yep, lua


def create_fake_globals(lua_instance):
    fake_user = User()
    fake_user.nickname = "TestUser"
    fake_user.username = "Testing"
    other_fake_user = User()
    other_fake_user.nickname = "teest2"
    other_fake_user.username = "mmmmm"
    fake_channel = Channel()
    fake_channel.name = "#fakechan"
    globalz = lua_instance.globals()
    globalz.users = [fake_user, other_fake_user]
    globalz.channels = [fake_channel]
    globalz.message_sender = fake_user
    globalz.hostname = util.HOSTNAME


def create_real_globals(lua_instance, server, sender_user):
    globz = lua_instance.globals()
    globz.users = server.users
    globz.channels = server.channels
    globz.message_sender = sender_user
    globz.server = server
    globz.hostname = util.HOSTNAME
    globz.motd = server.get_motd()


if __name__ == "__main__":
    # noinspection PyArgumentList
    lua_func, lua_inst = load_lua()
    create_fake_globals(lua_inst)
    lua_handle(lua_func, ":Server BRUH Yes No Maybe :So yeah")
    while True:
        time.sleep(1)
        if should_reload_lua():
            lua_func, lua_inst = load_lua()
            create_fake_globals(lua_inst)
            lua_handle(lua_func, ":Server BRUH Yes No Maybe :So yeah")
