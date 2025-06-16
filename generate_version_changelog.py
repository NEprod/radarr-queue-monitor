import datetime

# Read current version
try:
    with open("VERSION.txt", "r") as v_file:
        current_version = v_file.read().strip()
except FileNotFoundError:
    current_version = "v0.0.0"

print(f"Current version is {current_version}")
new_version = input("Enter new version (e.g. v1.1.2): ").strip()

print("Enter changelog details. Press Enter to add lines. Type DONE and press Enter when finished:")
lines = []
while True:
    line = input()
    if line.strip().upper() == "DONE":
        break
    lines.append(line)

changelog_message = "\n".join(lines)
today = datetime.date.today().isoformat()

# Update VERSION.txt
with open("VERSION.txt", "w") as v_file:
    v_file.write(new_version)

# Prepend new entry to CHANGELOG.md
new_entry = f"## {new_version} - {today}\n{changelog_message}\n\n"

try:
    with open("CHANGELOG.md", "r", encoding="utf-8") as c_file:
        existing = c_file.read()
except FileNotFoundError:
    existing = ""

with open("CHANGELOG.md", "w", encoding="utf-8") as c_file:
    c_file.write(new_entry + existing)

print(f"✅ Updated VERSION.txt and CHANGELOG.md for {new_version}")