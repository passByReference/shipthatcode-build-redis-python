from collections import defaultdict
import sys

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
        db[args[1]] = args[2]
        return "+OK\r\n"
    return _encode_error(f"ERR unknown command '{cmd}'")

def parse_integer(data: bytes, pos: int):
    crlf = data.find(b'\r\n', pos)
    if crlf == -1:
        raise ValueError("ERR. No crlf found. Invalid integer format")
    try:
        value = int(data[pos+1:crlf])
    except ValueError:
        raise ValueError("Invalid integer format")
    return value, crlf + 2  # skip \r\n   

def binary_parse(data:bytes, start: int):
    if data[start] != ord('*'):
        raise ValueError("Invalid RESP array format")
    n, pos = parse_integer(data, start)
    args = []
    for _ in range(n):
        if pos >= len(data) or data[pos] != ord('$'):
            raise ValueError("Invalid RESP bulk string format")
        length, pos = parse_integer(data, pos)
        if length == -1:
            args.append(None)
            continue
        if pos + length + 2 > len(data):
            raise ValueError("Not enough data for bulk string")
        bulk_string = data[pos:pos + length].decode('utf-8')
        args.append(bulk_string)
        pos += length + 2  # skip the bulk string and \r\n
    return args, pos

def main():
    data = sys.stdin.buffer.read()
    if not data:
        return
    pos = 0
    out = sys.stdout.buffer
    while pos < len(data):
        try:
            args, pos = binary_parse(data, pos)
            response = handle_command(args)
            out.write(response.encode('utf-8'))
            out.flush()
        except ValueError as e:
            out.write(_encode_error(str(e)).encode('utf-8'))
            out.flush()
            break  # Stop processing on error
    # for line in sys.stdin:
    #     line = line.strip()
    #     if not line:
    #         continue
    
    #     args = parse_args(line)
    #     response = handle_command(args)
    #     sys.stdout.write(response)
    #     sys.stdout.flush()


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
