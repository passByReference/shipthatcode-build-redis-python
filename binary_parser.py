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

