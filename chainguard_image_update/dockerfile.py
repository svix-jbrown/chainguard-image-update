import io
from dataclasses import dataclass


# read a single space-delimited word
def read_word(s: str) -> tuple[str, str]:
    chrs = []
    while s and not s[0].isspace():
        chrs.append(s[0])
        s = s[1:]
    return ("".join(chrs), s)


# chomp all text to the next EOL or EOF
def chomp_eol(s: str) -> str:
    while s:
        s = s[1:]
        if s and s[0] == "\n":
            break
    return s


def tokenize(s: str) -> list[str]:
    tokens = []
    token = []
    endquo = None

    def shift():
        if token:
            tokens.append("".join(token))
            token.clear()

    while s:
        if endquo is not None:
            if s.startswith(endquo):
                shift()
                s = s[len(endquo) :]
                endquo = None
            else:
                token.append(s[0])
                s = s[1:]
        elif s.startswith("#"):
            before = s
            s = chomp_eol(s)
            assert before != s
        elif s.startswith('"') or s.startswith("'"):
            endquo = s[0]
        elif s.startswith("<<"):
            s = s[2:]
            before = s
            (endquo, s) = read_word(s)
            assert before != s
        elif s[0].isspace():
            shift()
            s = s[1:]
        else:
            token.append(s[0])
            s = s[1:]
    if token:
        shift()

    return tokens


@dataclass
class Dockerfile:
    from_sources: list[str]


def parse_file(path: str) -> Dockerfile:
    with open(path) as f:
        return parse(f)


def parse(f: io.TextIOWrapper) -> Dockerfile:
    s = f.read()
    tokens = tokenize(s)
    from_sources = []
    for this_t, next_t in zip(tokens, tokens[1:]):
        if this_t == "FROM":
            from_sources.append(next_t)
    return Dockerfile(from_sources=from_sources)
