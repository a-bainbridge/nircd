function handle_cmd(input, time_mod)
    commands = grab_cmds(input)

    for k, command in pairs(commands) do
        if not command["malformed"] then
            name = command["command"]
            name = string.upper(name)
            if name == "CAP" then
                if message_sender == nil then
                    goto skip
                end
                if command.parameters[1] == "LS" then
                    message_sender.send_data_add_newlines_for_me("CAP * LS :nothing") --get mad
                end
            end
            if name == "PONG" then
                if message_sender == nil then
                    print("nil sender for ping?")
                    goto skip
                end
                message_sender.last_pong = time_mod.time()
            end
            if name == "PING" then
                if message_sender == nil then
                    goto skip
                end
                if exactly(1, command.parameters) then
                    message_sender.send_data_add_newlines_for_me(getHostString() .. " PONG " .. command.parameters[1])
                else
                    message_sender.send_data_add_newlines_for_me(getHostString() .. "PONG")
                end
            end
            if name == "NICK" then
                if not exactly(1, command.parameters) then
                    send_code("431", ":No nickname given")
                    goto skip
                end
                requested_nick = command.parameters[1]
                if not isValidNickname(requested_nick) then
                    send_code("432", requested_nick .. " :Erroneous nickname")
                    goto skip
                end
                if not (type(server.find_user_by_name(requested_nick)) == type(nil)) then
                    send_code("433", requested_nick .. " :Nickname is already in use")
                    goto skip
                end
                message_sender.update_nick(requested_nick) --todo move to lua?
            end
            if name == "USER" then
                if not message_sender.username == "*" then
                    send_code("462", ":Unauthorized command (already registered)")
                    goto skip
                end
                if not exactly(4, command.parameters) then
                    send_code("461", name .. " :Not enough parameters")
                    goto skip
                end
                username = command.parameters[1]
                realname = command.parameters[4]
                message_sender.username = "~" .. username
                message_sender.realname = realname
                message_sender.initialized = true
                send_welcome()
            end
            if name == "JOIN" then
                if not exactly(1, command.parameters) then
                    send_code("461", name .. " :Not enough parameters")
                    goto skip
                end
                --todo validate channel name according to RFC 2812
                cname = command.parameters[1]
                channels = {}
                for k, channel_name in pairs(split(cname, ",")) do
                    if channel_name == "" then
                        goto local_skip
                    end
                    maybe_channel = server.find_channel(channel_name)
                    if maybe_channel == nil then
                        send_code("403", cname .. " :No such channel")
                    end
                    if not isUserInChannel(message_sender, maybe_channel) then
                        maybe_channel.append_user(message_sender)
                        maybe_channel.send_join_msg(message_sender)
                        send_code(332, channel_name .. " :" .. maybe_channel.topic)
                        maybe_channel.send_names_list(message_sender)
                        message_sender.append_channel(maybe_channel)
                    end
                    ::local_skip::
                end
            end
            if name == "PRIVMSG" then
                if exactly(0, command.parameters) then
                    send_code("412", ":No text to send")
                    goto skip
                end
                if exactly(1, command.parameters) then
                    if string.sub(command.parameters, 1, 1) == ("#") then
                        send_code("412", ":No text to send")
                    else
                        send_code("411", ":No recipient given")
                    end
                    goto skip
                end
                if not exactly(2, command.parameters) then
                    --catch more than 2
                    send_code("412", ":No text to send")
                    goto skip
                end
                if string.sub(command.parameters[1], 1, 1) == ("#") then
                    maybe_channel = server.find_channel(command.parameters[1])
                    if maybe_channel == nil then
                        send_code("401", command.parameters[1] .. " :No such channel")
                        goto skip
                    end
                    maybe_channel.send_text_no_echo(message_sender, command.parameters[2])
                else
                    maybe_user = server.find_user_by_name(command.parameters[1])
                    if maybe_user == nil then
                        send_code("401", command.parameters[1] .. " :No such nick")
                        goto skip
                    end
                    maybe_user.send_data_add_newlines_for_me(":" .. message_sender.get_proper_name() .. " PRIVMSG " .. maybe_user.nickname .. " :" .. command.parameters[2])
                end
            end
            if name == "QUIT" then

            end
            :: skip ::
        end
    end

    return commands
end

function grab_cmds(input)
    -- python.builtins.getattr(message_sender, "initialized", false)
    commands = split(input, "\n")
    proper_cmds = {}
    for k, command in pairs(commands) do
        res, proper_cmd = xpcall(parse_message, debug.traceback, command)
        if res then
            table.insert(proper_cmds, proper_cmd)
        else
            --print(err)
        end
    end
    return proper_cmds
end
--
--    message    =  [ ":" prefix SPACE ] command [ params ] crlf
--    prefix     =  servername / ( nickname [ [ "!" user ] "@" host ] )
--    command    =  1*letter / 3digit
--    params     =  *14( SPACE middle ) [ SPACE ":" trailing ]
--               =/ 14( SPACE middle ) [ SPACE [ ":" ] trailing ]
--
--    nospcrlfcl =  %x01-09 / %x0B-0C / %x0E-1F / %x21-39 / %x3B-FF
--                    ; any octet except NUL, CR, LF, " " and ":"
--    middle     =  nospcrlfcl *( ":" / nospcrlfcl )
--    trailing   =  *( ":" / " " / nospcrlfcl )
--
--    SPACE      =  %x20        ; space character
--    crlf       =  %x0D %x0A   ; "carriage return" "linefeed"
--

-- input: a message
-- output: a table representation of the message
function parse_message(input)
    input = string.gsub(input, "\r", "")
    local rep = {}
    -- prefix
    if string.find(input, ":") == 1 then
        rep["prefix"] = split(input, " ")[1]
        input = string.gsub(input, rep["prefix"] .. " ", "", 1)
        rep["prefix"] = string.gsub(rep["prefix"], ":", "", 1)
    end
    -- command
    remaining = split(input, " ")
    maybe_command = remaining[1]
    if isAlphanumeric(maybe_command) then
        rep["command"] = maybe_command
        rep["malformed"] = false
    else
        rep["malformed"] = true
    end
    input = string.gsub(input, maybe_command, "", 1)
    if string.sub(input, 1, 1) == " " then
        input = string.gsub(input, " ", "", 1)
    end
    -- now the rest is parameters, right?
    rep["parameters"] = {}
    iter = 0
    while true do
        iter = iter + 1
        if iter > 99 then
            print("WTF!!")
        end
        if (string.len(input) == 0) then
            break
        else
            --print(input)
        end
        if string.sub(input, 1, 1) == ":" then
            table.insert(rep["parameters"], string.sub(input, 2))
            input = ""
        else
            param = split(input, " ")[1]
            table.insert(rep["parameters"], param)
            param = sanitize(param)
            input = string.gsub(input, param, "", 1)
            if string.sub(input, 1, 1) == " " then
                input = string.gsub(input, " ", "", 1)
            end
        end
    end
    return rep
end

function split (input, sep)
    if sep == nil then
        sep = "%s"
    end

    local t = {}

    for str in string.gmatch(input, "([^" .. sep .. "]+)") do
        table.insert(t, str)
    end

    return t
end

function sanitize (str)
    local bad_chars = "%-^$().[]*+"
    local str_copy
    for i = 1, #bad_chars do
        local c = bad_chars:sub(i, i)
        err, str_copy = pcall(string.gsub, str, "%" .. c, "%%" .. c)
        if err then
            str = str_copy
        end
    end
    return str
end

function isAlphanumeric(str)
    return string.gsub(str, "[%w]", "") == ""
end

function isValidNickname(str)
    return string.gsub(str, "[%w]", "") == "" and #str < 20
end

function exactly(num, thing)
    --just because
    return #thing == num
end

function atLeast(num, thing)
    return #thing >= num
end

function noMoreThan(num, thing)
    return #thing <= num
end

function getHostString()
    return ":" .. hostname
end

function send_code(code, message)
    send_code_to(code, message, message_sender)
end

function send_code_to(code, message, to)
    to.send_data_add_newlines_for_me(getHostString() .. " " .. code .. " " .. message_sender.nickname .. " " .. message)
end

function send_welcome()
    send_code("001", ":Welcome to " .. hostname)
    send_code("002", ":Your host is " .. hostname .. ", running version 1.0")
    send_code("003", ":This server was created 3/18/2020")
    send_code("004", hostname .. " 1.0 " .. "aio " .. "t")
    message_sender.send_ping()
    send_motd()
end

function isUserInChannel(user, channel)
    for i, cu in python.enumerate(channel.channel_users) do
        if cu == user then
            return true
        end
    end
    return false
end

function send_motd(to)
    if to == nil then
        to = message_sender
    end
    send_code_to(375, ":- " .. hostname .. " Message of the day - ", to)
    for k, line in pairs(split(server.get_motd(), "\n")) do
        send_code_to(372, line, to)
    end
    send_code_to(376, ":End of MOTD command", to)
end