"""Prints the order total per customer from a CSV export."""

import csv
import sys


def main(path):
    x = 0.0
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            x += float(row["total"])
    print(f"total={x:.2f}")


if __name__ == "__main__":
    main(sys.argv[1])
