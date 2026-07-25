from collections import defaultdict,deque
import re
import sys
import binary_parser

db = defaultdict()
lists = defaultdict(deque)
expiry_times = defaultdict()
clock = 0

def _encode_simple_string(s):
    """Encode a simple string in RESP format."""
    return f"+{s}\r\n"
def _encode_error(msg):
    """Encode an error message in RESP format."""
    return f"-{msg}\r\n"

def _encode_integer(n):
    """Encode an integer in RESP format."""
    return f":{n}\r\n"

def _encode_bulk_string(s):
    """Encode a bulk string in RESP format."""
    if s is None:
        return "$-1\r\n"
    return f"${len(s)}\r\n{s}\r\n"

def _encode_array(items):
    return f"*{len(items)}\r\n" + "".join(items)
def _incr_or_decr_key(key, amount, cmd):
    if cmd not in ("INCR", "DECR", "INCRBY", "DECRBY"):
        _encode_error(f"ERR {cmd} is not valid")
    if key not in db:
            db[key] = "0"
    
    db[key] = str(int(db[key]) + int(amount)) if "INCR" in cmd else str(int(db[key]) - int(amount))
    return db[key]

def _check_expiry(key):
    global clock
    return key in expiry_times and expiry_times[key] <= clock     
def _remove_expired_key(key):
    if _check_expiry(key):
        del db[key]
        del expiry_times[key]

def check_type(key):
    if key in db:
        return False
    return True

def normalize_index(index, length):
    if index < 0:
        index += length
    return index

def lpush(key, values):
    if not check_type(key):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    for value in values:
        lists[key].appendleft(value)
    return _encode_integer(len(lists[key]))
def rpush(key, values):
    if not check_type(key):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    for value in values:
        lists[key].append(value)
    return _encode_integer(len(lists[key]))

def lpop(key):
    if not check_type(key):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    if key not in lists:
        return None
    value = lists[key].popleft()
    if not lists[key]:
        del lists[key]
    return value
def rpop(key):
    if not check_type(key):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    if key not in lists:
        return None
    value = lists[key].pop()
    if not lists[key]:
        del lists[key]
    return value
def llen(key):
    return len(lists.get(key, ()))

def lrange(key, start, stop):
    dq = lists.get(key, deque())
    length = len(dq)
    start = normalize_index(start, length)
    stop = normalize_index(stop, length)
    start = max(start, 0)
    stop = min(stop, length - 1)
    if length == 0:
        return []
    return list(dq)[start:stop+1] if stop < length else list(dq)[start:length]

def handle_command(args):
    """Process a Redis command and return the RESP response."""
    global clock
    cmd = args[0].upper()

    if cmd == "PING":
        if len(args) > 2:
            return _encode_error("ERR wrong number of arguments for 'PING' command")
        if len(args) == 1:
            return _encode_simple_string("PONG")
        else:
            return _encode_bulk_string(args[1])
    elif cmd == "ECHO":
        if len(args) != 2:
            return _encode_error("ERR wrong number of arguments for 'ECHO' command")
        return _encode_bulk_string(args[1])
    elif cmd == "COMMAND":
        return "+OK\r\n"
    elif cmd == "EXISTS":
        if len(args) != 2:
            return _encode_error("ERR wrong number of arguments for 'EXISTS' command")
        key = args[1]
        _remove_expired_key(key)
        return _encode_integer(1 if key in db else 0)
    elif cmd == "GET":
        if len(args) != 2:
            return _encode_error("ERR wrong number of arguments for 'GET' command")
        key = args[1]
        _remove_expired_key(key)
        return _encode_bulk_string(db.get(key) if len(args) > 1 else None)
    elif cmd == "SET":
        if len(args) < 3:
            return _encode_error("ERR wrong number of arguments for 'SET' command")
        key = args[1]
        val = args[2]
        if len(args) == 4:
            # only NX|XX is allowed as the 4th argument
            cond = args[3].upper()
            if cond == "NX":
                if key in db:
                    return "$-1\r\n"
            elif cond == "XX":
                if key not in db:
                    return "$-1\r\n"
        if len(args) > 4:
            # parse optional arguments NX, XX, EX, PX
            nx = False
            xx = False
            ex = None
            px = None
            i = 3 
            while i < len(args):
                arg = args[i].upper()
                if arg == "NX":
                    nx = True
                    i += 1
                elif arg == "XX":
                    xx = True
                    i += 1
                elif arg == "EX":
                    if i + 1 >= len(args):
                        return _encode_error("ERR syntax error")
                    try:
                        ex = int(args[i + 1])
                        if ex <= 0:
                            return _encode_error("ERR invalid expire time in 'SET' command")
                    except ValueError:
                        return _encode_error("ERR invalid expire time in 'SET' command")
                    i += 2
                elif arg == "PX":
                    if i + 1 >= len(args):
                        return _encode_error("ERR syntax error")     
                    try:
                        px = int(args[i + 1])
                        if px <= 0:
                            return _encode_error("ERR invalid expire time in 'SET' command")
                    except ValueError:
                        return _encode_error("ERR invalid expire time in 'SET' command")
                    i += 2
            if ex is not None and px is not None:
                return _encode_error("ERR syntax error")
            if nx and xx:
                return _encode_error("ERR syntax error")
            if nx and key in db:
                return "$-1\r\n"
            if xx and key not in db:
                return "$-1\r\n"
            if ex:
                expiry_times[key] = clock + ex
            elif px:
                expiry_times[key] = clock + px / 1000
         
        db[key] = val
        return "+OK\r\n"
    elif cmd == "DBSIZE":
        return _encode_integer(len(db))
    elif cmd == "INCRBY" or cmd == "DECRBY":
        if len(args) != 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        amount = args[2]
        try:
            new_val = _incr_or_decr_key(key, amount, cmd)
            return _encode_integer(new_val)
        except Exception:
            return _encode_error("ERR value is not an integer or out of range")
        
    elif cmd == "INCR" or cmd == "DECR":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        try:
            new_val = _incr_or_decr_key(key, 1, cmd)
            return _encode_integer(new_val)
        except Exception:
            return _encode_error("ERR value is not an integer or out of range")
    elif cmd == "EXPIRE":
        if len(args) != 3:
            return _encode_error(f"ERR wrong number of aruguments for '{cmd}' command")
        key = args[1]
        ttl_seconds = args[2]
        if key not in db:
            return _encode_integer(0)
        try:
            expiry_times[key] = clock + int(ttl_seconds)
        except Exception:
            return _encode_error(f"ERR {ttl_seconds} is not an integer or out of range")
        return _encode_integer(1)
    elif cmd == "TTL" or cmd == "PTTL":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        if key not in db:
            return _encode_integer(-2)
        if key in expiry_times:
            if _check_expiry(key):
                _remove_expired_key(key)
                return _encode_integer(-2)
            return _encode_integer(expiry_times[key] - clock if cmd == "TTL" else int(expiry_times[key] - clock) * 1000)
        return _encode_integer(-1)
    elif cmd == "PERSIST":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        if key not in expiry_times:
            return _encode_integer(0)
        del expiry_times[key]
        return _encode_integer(1)
    elif cmd == "WAIT":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        try:
            n = int(args[1])
            if n < 0:
                return _encode_error(f"ERR {n} is not a valid integer")
            clock += n / 1000
        except Exception:
            return _encode_error(f"ERR {args[1]} is not a valid integer")
        return _encode_simple_string("OK")
    elif cmd == "LPUSH":
        if len(args) < 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        values = args[2:]
        return lpush(key, values)
    elif cmd == "RPUSH":
        if len(args) < 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        values = args[2:]
        return rpush(key, values)
    elif cmd == "LPOP":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        value = lpop(key)
        return _encode_bulk_string(value)
    elif cmd == "RPOP":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        value = rpop(key)
        return _encode_bulk_string(value)
    elif cmd == "LLEN":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        length = llen(key)
        return _encode_integer(length)
    elif cmd == "LRANGE":
        if len(args) != 4:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        try:
            start = int(args[2])
            stop = int(args[3])
        except Exception:
            return _encode_error(f"ERR {args[2]} or {args[3]} is not a valid integer")
        result = lrange(key, start, stop)
        return _encode_array([_encode_bulk_string(item) for item in result])
    return _encode_error(f"ERR unknown command '{cmd}'")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
    
        args = parse_args(line)
        response = handle_command(args)
        sys.stdout.write(response)
        sys.stdout.flush()
    
    ### Binary parser below ####
    # data = sys.stdin.buffer.read()
    # if not data:
    #     return
    # pos = 0
    # out = sys.stdout.buffer
    # while pos < len(data):
    #     try:
    #         args, pos = binary_parser.binary_parse(data, pos)
    #         response = handle_command(args)
    #         out.write(response.encode('utf-8'))
    #         out.flush()
    #     except ValueError as e:
    #         out.write(_encode_error(str(e)).encode('utf-8'))
    #         out.flush()
    #         break  # Stop processing on error


def parse_args(line):
    """Split a command line into arguments, handling quoted strings."""
    args = []
    current = ""
    in_quotes = False
    for ch in line:
        if ch == '"' and not in_quotes:
            in_quotes = True
        elif ch == '"' and in_quotes:
            in_quotes = False
        elif ch == ' ' and not in_quotes:
            if current:
                args.append(current)
                current = ""
        else:
            current += ch
    if current:
        args.append(current)
    return args

if __name__ == "__main__":
    main()
