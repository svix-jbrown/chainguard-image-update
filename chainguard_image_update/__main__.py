import argparse
import difflib
import json
import os
import re
import subprocess
from dataclasses import dataclass

from . import dockerfile

_SOURCE_RE = re.compile(r"^cgr\.dev/(?P<org>[^/]+)/(?P<repo>[^@:]+)(?::(?P<tag>[^@:]+))?@(?P<digest>.+)$")


@dataclass
class ChainguardSource:
    org: str
    repo: str
    tag: str | None
    digest: str

    @classmethod
    def parse(cls, s: str) -> "ChainguardSource":
        if md := _SOURCE_RE.match(s):
            return cls(repo=md.group("repo"), tag=md.group("tag"), digest=md.group("digest"), org=md.group("org"))
        else:
            raise ValueError(f"Invalid source {s}")

    @property
    def key(self) -> str:
        return f"{self.repo}:{self.effective_tag}"

    @property
    def effective_tag(self) -> str:
        if self.tag is None:
            return "latest"
        return self.tag


class LookerUpper:
    def __init__(self):
        self.latest_versions = {}

    def lookup(self, source: ChainguardSource) -> str:
        if source.key not in self.latest_versions:
            command = ["chainctl", "images", "tags", "list", "--repo", source.repo, "-o", "json"]
            if source.org == "chainguard":
                command += ["--public"]
            data = subprocess.check_output(command)
            data = json.loads(data)
            for row in data:
                if row["name"] == source.effective_tag:
                    self.latest_versions[source.key] = row["digest"]
                    break
            else:
                raise ValueError(f"Failed to find a version for {source}")
        return self.latest_versions[source.key]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--dry-run", action="store_true")
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        default=[],
        help="Filename to process (may be repeated; if not passed, will search recursively)",
    )
    parser.add_argument("-d", "--chdir", help="chdir to this path before running")
    args = parser.parse_args()

    if args.chdir:
        os.chdir(args.chdir)

    targets = args.file
    if not targets:
        for dir, dirs, files in os.walk(".", topdown=True):
            for p in (".git", ".hg", ".terraform", "node_modules", "venv", ".venv"):
                if p in dirs:
                    dirs.remove(p)
            for file in files:
                if "dockerfile" in file.lower():
                    targets.append(os.path.join(dir, file))
    lu = LookerUpper()
    for target in targets:
        parsed = dockerfile.parse_file(target)
        conversions = {}
        for source in parsed.from_sources:
            if "cgr.dev/" in source:
                if "@" in source:
                    source = ChainguardSource.parse(source)
                    expected = lu.lookup(source)
                    if source.digest != expected:
                        conversions[source.digest] = expected
                else:
                    raise ValueError("un-digested chainguard source found")
        if conversions:
            original = []
            rewritten = []
            with open(target) as f:
                for line in f:
                    line = line.rstrip()
                    original.append(line)
                    for source, dest in conversions.items():
                        if source in line:
                            line = line.replace(source, dest)
                    rewritten.append(line)
            if args.dry_run:
                for line in difflib.unified_diff(original, rewritten, fromfile=target, tofile=f"{target}.updated"):
                    print(line)
                print()
            else:
                with open(target, "w") as f:
                    for line in rewritten:
                        f.write(line)
                        f.write("\n")


if __name__ == "__main__":
    main()
