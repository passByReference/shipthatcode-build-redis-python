import sys

def handle_command(args):
    """Process a Redis command and return the RESP response."""
    cmd = args[0].upper()

    if cmd == "PING":
        if len(args) == 1:
            return "+PONG\r\n"
        else:
            return f"${len(args[1])}\r\n{args[1]}\r\n"
        # TODO: Return +PONG\r\n for no args
        # TODO: Return bulk string for PING <message>
    elif cmd == "ECHO":
        if len(args) != 2:
            return "-ERR wrong number of arguments for 'ECHO' command\r\n"
        return f"${len(args[1])}\r\n{args[1]}\r\n"
    return "-ERR unknown command\r\n"

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        args = parse_args(line)
        response = handle_command(args)
        sys.stdout.write(response)
        sys.stdout.flush()

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
