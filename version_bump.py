import subprocess
import re

# Read version from VERSION.txt
try:
    with open("VERSION.txt", "r") as f:
        version = f.read().strip()
except FileNotFoundError:
    print("❌ VERSION.txt not found.")
    exit(1)

# Read changelog section for this version
try:
    with open("CHANGELOG.md", "r", encoding="utf-8") as f:
        changelog = f.read()
except FileNotFoundError:
    print("❌ CHANGELOG.md not found.")
    exit(1)

# Extract just this version's changelog title
match = re.search(rf"^##\s+{re.escape(version)}\s+-\s+.*", changelog, re.MULTILINE)
if not match:
    print(f"❌ No version title found for {version}")
    exit(1)

# Strip the leading "## " from the title line
message = match.group(0).replace("## ", "", 1).strip()

# Create annotated tag
try:
    subprocess.run(["git", "tag", "-a", version, "-m", message], check=True)
    print(f"✅ Created annotated Git tag: {version}")
except subprocess.CalledProcessError:
    print("❌ Failed to create Git tag.")

# Optional: Uncomment to push the tag
# subprocess.run(["git", "push", "origin", version])