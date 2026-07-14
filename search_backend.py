import os

for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".py") or file.endswith(".sql"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "tires_laps_current" in content or "chain_hours_current" in content:
                        print(f"Found in {path}")
            except:
                pass
