"""
Convert Microsoft's AdventureWorks CSVs into the format the PostgreSQL
port's install.sql loads, without Ruby.

    python datasets/adventureworks/prepare_data.py

A line-by-line port of update_csvs.rb from lorint/AdventureWorks-for-Postgres
(pinned commit in SOURCES.md), including Ruby's semantics where they matter:
String#strip also removes NUL, and String#split drops trailing empty fields.
Unlike the original, it leaves the downloaded files untouched and writes
every CSV (converted or copied) to data/converted/, which import.sql uses.
"""

import os
import re
import shutil

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT_DIR = os.path.join(DATA_DIR, "converted")

# Ruby's whitespace for strip: null, \t, \n, \v, \f, \r, space.
RUBY_WS = "\0\t\n\v\f\r "


def ruby_strip(text):
    return text.strip(RUBY_WS)


def ruby_lines(text):
    """Split like Ruby's IO#each: on \\n only, keeping the terminator."""
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def ruby_split(text, separator):
    """String#split with a string pattern: trailing empty fields dropped."""
    if not text:
        return []
    parts = text.split(separator)
    while parts and parts[-1] == "":
        parts.pop()
    return parts


def convert_field(part, index):
    # Newer files can hold an actual NUL as a hierarchyid value; text
    # cannot store NUL, and install.sql expects hex text.
    if index == 0 and part == "\0":
        part = "00"
    else:
        part = part.replace("\0", "")

    if part[:1] == "<" and part[-1:] == ">":
        return '"' + part + '"'
    if part[1:2] == "<" and part[-1:] == ">":
        return '"' + part[1:] + '"'
    if "\t" in part:
        return '"' + part + '"'
    return part


def convert(text):
    """The converted text, or None if the file needs no conversion."""
    lines = ruby_lines(text)
    if not lines:
        return None

    first = lines[0]
    needed = is_pipes = is_cleaning = False

    if "+|" in first:
        is_pipes = needed = is_cleaning = True
    if first.startswith("﻿"):
        lines[0] = first = first[1:]
        needed = True
    if "&|" in first or "\tE6100000010C" in first:
        needed = is_cleaning = True

    if not needed:
        return None

    output = []
    record = ""

    for line in lines:
        if is_pipes:
            line = line.replace("|474946383961", "|\\x474946383961")  # GIF data
            line = line.replace('"', '""')

            while (end := line.find("&|")) != -1:
                record += ruby_strip(line[:end])
                fields = ruby_split(record, "+|")
                output.append(
                    "\t".join(convert_field(f, i) for i, f in enumerate(fields))
                )
                output.append("\n")
                record = ""
                line = line[end + 2:]

            if ruby_strip(line):
                record += re.sub(r"\r?\n", r"\\n", line)
        elif is_cleaning:
            line = line.replace('"', '""')
            line = line.replace("&|\n", "\n").replace("&|\r\n", "\n")
            line = line.replace("\tE6100000010C", "\t\\xE6100000010C")  # geospatial
            line = line.replace("\r\n", "\n")
            output.append(line)
        else:
            output.append(line)

    return "".join(output)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    converted = copied = 0
    for name in sorted(os.listdir(DATA_DIR)):
        if not name.endswith(".csv"):
            continue

        source = os.path.join(DATA_DIR, name)
        target = os.path.join(OUT_DIR, name)

        with open(source, "r", encoding="utf-8", newline="") as file:
            result = convert(file.read())

        if result is None:
            shutil.copyfile(source, target)
            copied += 1
        else:
            with open(target, "w", encoding="utf-8", newline="") as file:
                file.write(result)
            print(f"Converted {name}")
            converted += 1

    print(f"{converted} converted, {copied} copied unchanged -> {OUT_DIR}")


if __name__ == "__main__":
    main()
