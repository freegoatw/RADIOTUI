def parse(inp: str):
    try:
        tokens = inp.split()
        
        if not tokens:
            return None
        if tokens[0] == "quit" or tokens[0] == "exit" or tokens[0] == "logout":
            return -1

        if len(tokens) == 1:
            return {
                'sys': tokens[0]
            }
        
        sys = tokens[0]
        action = tokens[1]
        flags = {}
        name_parts = []

        for i in tokens[2:]:
            if i.startswith("--"):
                key, val = i.split("=", 1)
                key = key[2:]
                flags[key] = val
            else:
                name_parts.append(i)

        name = " ".join(name_parts) if name_parts else None
        out = {
            'sys': sys,
            'action': action,
            'name': name
        }
        return out | flags
        
    except:
        return None
    
    
