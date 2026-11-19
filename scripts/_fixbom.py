from pathlib import Path

p = Path(r"D:\云旅ai\scripts\check.ps1")
data = p.read_bytes()
bom = b"\xef\xbb\xbf"
while data.startswith(bom):
    data = data[len(bom):]
p.write_bytes(bom + data)
print(p.read_bytes()[:10])