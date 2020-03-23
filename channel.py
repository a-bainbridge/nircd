from user import User
from util import HOSTNAME


class Channel(object):
    channel_users = []
    name = ""
    topic = ""

    def __init__(self):
        self.channel_users = []
        self.name = ""
        self.topic = ""

    def send_text(self, source, text):
        self.send_to_all(":" + source + " PRIVMSG " + self.name + " :" + text)

    def send_text_no_echo(self, source: User, text):
        self.send_exclusive(":" + source.get_proper_name() + " PRIVMSG " + self.name + " :" + text, source)

    def send_to_all(self, data: str):
        for user in self.channel_users:
            try:
                user.send_data_add_newlines_for_me(data.replace("%s", user.nickname))
            except:
                print("oops")

    def send_exclusive(self, data, user_skip: User):
        for user in self.channel_users:
            if user == user_skip:
                continue
            try:
                user.send_data_add_newlines_for_me(data)
            except:
                print("oops")

    def send_join_msg(self, user: User):
        self.send_to_all(":" + user.get_proper_name() + " JOIN :" + self.name)

    def disconnect_quit(self, user: User, reason: str):
        if user in self.channel_users:
            self.send_to_all(":" + user.nickname + " QUIT :" + reason)
            self.channel_users.remove(user)

    def disconnect_part(self, user: User, reason: str):
        if user in self.channel_users:
            self.send_to_all(":" + user.nickname + " PART "+self.name+" :" + reason)
            self.channel_users.remove(user)

    def send_nick(self, user: User, new_name):
        self.send_exclusive(":" + user.nickname + " NICK " + new_name, user)

    def send_names_list(self, user: User):
        buf = ""
        for chanuser in self.channel_users:
            buf = buf + ":"+HOSTNAME+" 353 "+user.nickname+" = " + self.name + " :" + chanuser.nickname + "\r\n"
        buf = buf + ":"+HOSTNAME+" 366 "+user.nickname+" " + self.name + " :End of /NAMES list"
        user.send_data_add_newlines_for_me(buf)

    def append_user(self, user):
        self.channel_users.append(user)
