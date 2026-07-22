from collections import defaultdict
import sys
import binary_parser

db = defaultdict()

def _encode_simple_string(s):
    """Encode a simple string in RESP format."""
    return f"+{s}\r\n"
def _encode_error(msg):
    """Encode an error message in RESP format."""
    return f"-{msg}\r\n"

def _encode_integer(n):
    """Encode an integer in RESP format."""
    return f":{n}\r\n"

def encode_bulk_string(s):
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
    
def handle_command(args):
    """Process a Redis command and return the RESP response."""
    cmd = args[0].upper()

    if cmd == "PING":
        if len(args) > 2:
            return _encode_error("ERR wrong number of arguments for 'PING' command")
        if len(args) == 1:
            return _encode_simple_string("PONG")
        else:
            return encode_bulk_string(args[1])
    elif cmd == "ECHO":
        if len(args) != 2:
            return _encode_error("ERR wrong number of arguments for 'ECHO' command")
        return encode_bulk_string(args[1])
    elif cmd == "COMMAND":
        return "+OK\r\n"
    elif cmd == "GET":
        return encode_bulk_string(db.get(args[1]) if len(args) > 1 else None)
    elif cmd == "SET":
        if len(args) < 3:
            return _encode_error("ERR wrong number of arguments for 'SET' command")
        key = args[1]
        val = args[2]
        if len(args) > 3:
            cond = args[3].upper()
            if cond == "NX":
                if key in db:
                    return "$-1\r\n"
            elif cond == "XX":
                if key not in db:
                    return "$-1\r\n"
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
