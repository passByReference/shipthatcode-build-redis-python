from collections import defaultdict,deque
import re
import sys
import binary_parser

db = defaultdict()
lists = defaultdict(deque)
hashes = defaultdict(dict)
expiry_times = defaultdict()
existing_types = defaultdict()
sets = defaultdict(set)
zset = defaultdict(dict)
existing_types['string'] = db
existing_types['list'] = lists
existing_types['hash'] = hashes
existing_types['set'] = sets
existing_types['zset'] = zset
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

def check_type(key, type_in_use=None):
    for type_name, type_dict in existing_types.items():
        if type_name == type_in_use:
            continue
        if key in type_dict:
            return False
    return True

def normalize_index(index, length):
    if index < 0:
        index += length
    return index

def lpush(key, values):
    if not check_type(key, "list"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    for value in values:
        lists[key].appendleft(value)
    return _encode_integer(len(lists[key]))
def rpush(key, values):
    if not check_type(key, "list"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    for value in values:
        lists[key].append(value)
    return _encode_integer(len(lists[key]))

def lpop(key):
    if not check_type(key, "list"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    if key not in lists:
        return None
    value = lists[key].popleft()
    if not lists[key]:
        del lists[key]
    return value
def rpop(key):
    if not check_type(key, "list"):
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
def hset(key, pairs):
    if not check_type(key, "hash"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    count = 0
    for field, value in pairs.items():
        if field not in hashes[key]:
            count += 1
        hashes[key][field] = value
    return count

def hget(key, field):
    if not check_type(key, "hash"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    return hashes[key].get(field, None)

def hdel(key, fields):
    if not check_type(key, "hash"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    count = 0
    for field in fields:
        if field in hashes[key]:
            del hashes[key][field]
            count += 1
    if not hashes[key]:
        del hashes[key]
    return count

def hgetall(key):
    if not check_type(key, "hash"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    result = []
    for field, value in hashes[key].items():
        result.append(field)
        result.append(value)
    return result

def hexists(key, field):
    if not check_type(key, "hash"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    return 1 if field in hashes[key] else 0

def hlen(key):
    if not check_type(key, "hash"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    return len(hashes[key])

def sadd(key, members):
    if not check_type(key, "set"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    count = 0
    for member in members:
        if member not in sets[key]:
            sets[key].add(member)
            count += 1
    return count

def smem(key):
    if not check_type(key, "set"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    return list(sets[key])

def sismember(key, member):
    if not check_type(key, "set"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    return 1 if member in sets[key] else 0

def scard(key):
    if not check_type(key, "set"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    return len(sets[key])

def srem(key, members):
    if not check_type(key, "set"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    count = 0
    for member in members:
        if member in sets[key]:
            sets[key].remove(member)
            count += 1
    if not sets[key]:
        del sets[key]
    return count

def zadd(key, pairs):
    if not check_type(key, "zset"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    count = 0
    for score, member in pairs.items():
        if member not in zset[key]:
            count += 1
        zset[key][member] = int(score)
    return count

def zscoe(key, member):
    if not check_type(key, "zset"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    return zset[key].get(member, None)

def zrange(key, start, stop):
    if not check_type(key, "zset"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    sorted_members = sorted(zset[key].items(), key=lambda x: x[1])
    length = len(sorted_members)
    # this is key point - normalization
    start = normalize_index(start, length)
    stop = normalize_index(stop, length)
    start = max(start, 0)
    stop = min(stop, length - 1)
    if length == 0:
        return []
    return [member for member, score in sorted_members[start:stop+1]]

def zrank(key, member):
    if not check_type(key, "zset"):
        return _encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
    sorted_members = sorted(zset[key].items(), key=lambda x: x[1])
    for index, (m, score) in enumerate(sorted_members):
        if m == member:
            return index
    return None
   
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
    elif cmd == "HSET":
        if len(args) < 4 or len(args) % 2 != 0:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        pairs = dict(zip(args[2::2], args[3::2]))
        count = hset(key, pairs)
        return _encode_integer(count)
    elif cmd == "HGET":
        if len(args) != 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        field = args[2]
        value = hget(key, field)
        return _encode_bulk_string(value)
    elif cmd == "HDEL":
        if len(args) < 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        fields = args[2:]
        count = hdel(key, fields)
        return _encode_integer(count)
    elif cmd == "HGETALL":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        return _encode_array([_encode_bulk_string(item) for item in hgetall(key)])
    elif cmd == "HEXISTS":
        if len(args) != 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        field = args[2]
        exists = hexists(key, field)
        return _encode_integer(exists)
    elif cmd == "HLEN":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        length = hlen(key)
        return _encode_integer(length)
    elif cmd == "SADD":
        if len(args) < 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        members = args[2:]
        count = sadd(key, members)
        return _encode_integer(count)
    elif cmd == "SMEMBERS":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        members = smem(key)
        return _encode_array([_encode_bulk_string(member) for member in members])
    elif cmd == "SISMEMBER":
        if len(args) != 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        member = args[2]
        is_member = sismember(key, member)
        return _encode_integer(is_member)
    elif cmd == "SCARD":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        count = scard(key)
        return _encode_integer(count)
    elif cmd == "SREM":
        if len(args) < 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        members = args[2:]
        count = srem(key, members)
        return _encode_integer(count)
    elif cmd == "ZADD":
        if len(args) < 4 or len(args) % 2 != 0:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        pairs = dict(zip(args[2::2], args[3::2]))
        try:
            count = zadd(key, pairs)
            return _encode_integer(count)
        except Exception:
            return _encode_error("ERR score is not a valid float")
    elif cmd == "ZSCORE":
        if len(args) != 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        member = args[2]
        score = zscoe(key, member)
        return _encode_bulk_string(str(score) if score else None)
    elif cmd == "ZRANGE":
        if len(args) > 5 or len(args) < 4:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        try:
            start = int(args[2])
            stop = int(args[3])
            with_scores = len(args) == 5 and args[4].upper() == "WITHSCORES"
        except Exception:
            return _encode_error(f"ERR {args[2]} or {args[3]} is not a valid integer")
        result = zrange(key, start, stop)
        if with_scores:
            result_with_scores = []
            for member in result:
                score = zset[key][member]
                result_with_scores.append(member)
                result_with_scores.append(str(score))
            return _encode_array([_encode_bulk_string(item) for item in result_with_scores])
        else:
            return _encode_array([_encode_bulk_string(item) for item in result])
    elif cmd == "ZRANK":
        if len(args) != 3:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        member = args[2]
        rank = zrank(key, member)
        return _encode_integer(rank if rank is not None else None)
    elif cmd == "ZCARD":
        if len(args) != 2:
            return _encode_error(f"ERR wrong number of arguments for '{cmd}' command")
        key = args[1]
        count = len(zset[key]) if key in zset else 0
        return _encode_integer(count)
     
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
